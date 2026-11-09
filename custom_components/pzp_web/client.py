"""Local PZP/Teco web client; no writes on connection or recovery.

Only explicitly observed firmware symbols are allowed. A failed write is never
replayed: the controller's H111 command is a toggle, not an idempotent setter.
"""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import threading
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SEASONS = ("Topná sezóna", "Léto")
SEASON_SYMBOL = "__TC9AFA189_SINT_d"
EXPECTED_PAGE_VERSION = "1599547397"
SCHEDULES = {
    'R046': {'page':'/PAGE71.XML', 'version':'1642510300', 'command':'__T839E21A3_USINT_u'},
    'M146': {'page':'/PAGE68.XML', 'version':'1642510299', 'command':'__TBB632BEE_USINT_u'},
    'O039': {'page':'/PAGE25.XML', 'version':'1642510295', 'command':'__T6CF4DF44_USINT_u'},
    'C003': {'page':'/PAGE324.XML', 'version':'1642510295', 'command':'__T1939E5E1_USINT_u'},
}
SCHEDULE_NAVIGATION = {'previous_day':1, 'next_day':2, 'previous_time':3, 'next_time':4}


class PzpError(Exception):
    """A sanitized device error, without credentials or session contents."""


class AuthError(PzpError):
    """Credentials were rejected or the session expired."""


class UnsupportedFirmware(PzpError):
    """The page does not match the verified firmware layout."""


class WriteUncertain(PzpError):
    """A command may have arrived; it must not be retried automatically."""


def normalize_host(host):
    """Normalize a local IPv4/DNS authority without accepting URLs or credentials."""
    if not isinstance(host, str):
        raise ValueError('Zadejte IP adresu nebo název zařízení bez cesty.')
    value = host.strip().lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?', value):
        raise ValueError('Zadejte IP adresu nebo název zařízení bez cesty.')
    name, separator, port = value.partition(':')
    if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
           for label in name.split('.')) or len(name) > 253:
        raise ValueError('Neplatný název zařízení.')
    if separator:
        if not 1 <= int(port) <= 65535:
            raise ValueError('Neplatný port zařízení.')
        return name if int(port) == 80 else f'{name}:{int(port)}'
    return name


class LocalRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.netloc != self.host or parsed.scheme != "http":
            raise PzpError("Regulátor přesměroval spojení na jiný server.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PzpClient:
    def __init__(self, host, username, password, *, timeout=8):
        host = normalize_host(host)
        self.host = host
        self.base = "http://" + host
        self.username = username
        self._password = password
        self.timeout = timeout
        self._lock = threading.RLock()
        self._logged_in = False
        catalog_path = Path(__file__).with_name('catalog.json')
        self.catalog = {c['code']: c for c in json.loads(catalog_path.read_text(encoding='utf-8'))} if catalog_path.exists() else {}
        admin_path = Path(__file__).with_name('admin_catalog.json')
        self.admin_catalog = json.loads(admin_path.read_text(encoding='utf-8')) if admin_path.exists() else {}
        self._admin_tokens = {}
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            LocalRedirects(host), urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def _request(self, path, data=None, *, xml=False):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Only local absolute paths are allowed")
        headers = {"User-Agent": "HomeAssistant-PZP/0.1", "Referer": self.base + path}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if xml:
            headers["x-tecomat"] = "data"
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise PzpError("Odpověď regulátoru je příliš velká.")
                return response.url, body.decode("utf-8-sig")
        except (urllib.error.URLError, OSError, UnicodeError) as exc:
            # Never expose request contents, cookies or login response bodies.
            raise PzpError("Čerpadlo neodpovídá nebo odmítlo požadavek.") from None

    @staticmethod
    def _is_login(url, body):
        return "/SYSWWW/LOGIN.XML" in url.upper() or "<LOGIN>" in body

    def _login(self):
        self._logged_in = False
        self.cookies.clear()
        self._request("/SYSWWW/LOGIN.XML")
        challenge = next((c.value for c in self.cookies if c.name == "SoftPLC"), None)
        if not challenge:
            raise UnsupportedFirmware("Regulátor neposkytl očekávané přihlášení SoftPLC.")
        digest = hashlib.sha1(
            (urllib.parse.unquote(challenge) + self._password).encode("utf-8")
        ).hexdigest()
        payload = urllib.parse.urlencode({"USER": self.username, "PASS": digest}).encode()
        url, body = self._request("/SYSWWW/LOGIN.XML", payload)
        if self._is_login(url, body):
            raise AuthError("Čerpadlo nepřijalo přihlašovací údaje.")
        self._logged_in = True

    def _read_page(self, path):
        if not self._logged_in:
            self._login()
        url, body = self._request(path, xml=True)
        if self._is_login(url, body):
            self._logged_in = False
            self._login()
            url, body = self._request(path, xml=True)
        if self._is_login(url, body):
            raise AuthError("Přihlášení k čerpadlu vypršelo.")
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            raise UnsupportedFirmware("Čerpadlo vrátilo neznámý formát dat.") from None
        if root.tag != "PAGE":
            raise UnsupportedFirmware("Čerpadlo nevrátilo stránku parametrů.")
        return root

    @staticmethod
    def parse_season_page(root):
        access = root.find("ACCESS")
        values = [i.get("VALUE", "") for i in root.findall("INPUT")]
        if len(values)>=12:
            values[5]={'Winter':'Topná sezóna','Sommer':'Léto'}.get(values[5],values[5])
            values[4]={'Manuel':'Ruční'}.get(values[4],values[4])
        if (access is None or access.get("UCID") != EXPECTED_PAGE_VERSION
                or len(values) < 12 or values[5] not in SEASONS
                or values[2] not in ("Volba období","Auswahl des Zeitraumes")):
            raise UnsupportedFirmware("Rozložení H111 neodpovídá ověřenému firmware.")
        return {"season": values[5], "period_mode": values[4],
                "summer_heating": values[8], "winter_cooling": values[11],
                "season_visible": values[1] != "0"}

    def read_state(self):
        with self._lock:
            return self.parse_season_page(self._read_page("/PAGE40.XML"))

    def set_season(self, desired):
        if desired not in SEASONS:
            raise ValueError("Neplatná sezóna")
        with self._lock:
            current = self.read_state()
            if not current["season_visible"]:
                raise PzpError("Regulátor nyní ruční volbu sezóny nenabízí.")
            if current["period_mode"] != "Ruční":
                raise PzpError("Pro volbu sezóny musí být změna období v režimu Ruční.")
            if current["season"] == desired:
                return current
            # Match the controller's own encodeURIComponent(name + '=99').
            payload = urllib.parse.quote(SEASON_SYMBOL + "=99", safe="~()*!.'-").encode()
            try:
                url, body = self._request("/PAGE40.XML", payload)
                if self._is_login(url, body):
                    self._logged_in = False
            except PzpError:
                # The write may have succeeded despite a lost response.
                pass
            # Only READS after the one write, including an ambiguous response.
            for attempt in range(3):
                time.sleep(0.6)
                try:
                    current = self.read_state()
                    if current["season"] == desired:
                        return current
                except PzpError:
                    break
            raise WriteUncertain(
                "Změnu nelze potvrdit. Příkaz se neopakuje; po obnovení spojení "
                "se načte skutečný stav čerpadla."
            )

    def _parameter_value(self, cfg, root):
        access = root.find('ACCESS')
        inputs = root.findall('INPUT')
        index = cfg['index']
        if access is None or access.get('UCID') != cfg['version'] or len(inputs) <= index:
            raise UnsupportedFirmware('Změnilo se rozložení stránky parametru ' + cfg['code'])
        if inputs[index].get('NAME') != cfg['value_symbol']:
            raise UnsupportedFirmware('Nesouhlasí identifikace parametru ' + cfg['code'])
        visible = cfg.get('visible_index')
        available = visible is None or (visible < len(inputs) and inputs[visible].get('VALUE') != '0')
        value=inputs[index].get('VALUE')
        if value in ('Ja','Nein'):value={'Ja':'Ano','Nein':'Ne'}[value]
        return {'value': value, 'available': available}

    def read_all(self):
        with self._lock:
            state = self.read_state()
            pages = {}
            values = {}
            for code, cfg in self.catalog.items():
                page = cfg['page']
                if page not in pages:
                    try:
                        pages[page] = self._read_page(page)
                    except PzpError:
                        pages[page] = None
                try:
                    if pages[page] is None:
                        raise PzpError('Stránka není dostupná')
                    values[code] = self._parameter_value(cfg, pages[page])
                except PzpError:
                    values[code] = {'value': None, 'available': False}
            state['parameters'] = values
            return state

    def _post_command(self, page, symbol, value):
        payload = urllib.parse.quote(symbol + '=' + str(value), safe="~()*!.'-").encode()
        url, body = self._request(page, payload)
        if self._is_login(url, body):
            self._logged_in = False
            raise AuthError('Přihlášení vypršelo před dokončením změny.')

    def _editor_value(self, cfg):
        root = self._read_page(cfg['editor'])
        access = root.find('ACCESS')
        values = [n.get('VALUE','') for n in root.findall('INPUT')]
        if (access is None or access.get('UCID') != cfg['editor_version'] or len(values) != 3
                or not values[1].startswith(cfg['code'] + ':')):
            raise UnsupportedFirmware('Editor neodpovídá zvolenému parametru; změna se neuloží.')
        return values[0]

    def set_numeric(self, code, requested, *, force_same_value=False):
        cfg = self.catalog[code]
        if cfg['kind'] != 'numeric':
            raise ValueError('Tento parametr není číselný.')
        text = str(requested).strip().replace(',', '.')
        pattern = r'-?\d+(?:\.\d)?' if cfg['decimals'] else r'\d+'
        if len(text) > 9 or not re.fullmatch(pattern, text):
            raise ValueError('Zadejte platné číslo' + (' s nejvýše jedním desetinným místem.' if cfg['decimals'] else '.'))
        desired = Decimal(text)
        with self._lock:
            before = self._parameter_value(cfg, self._read_page(cfg['page']))
            if not before['available']:
                raise PzpError('Regulátor tento parametr v současném režimu nenabízí.')
            if Decimal(before['value']) == desired and not force_same_value:
                return before['value']
            # Open the controller's own editor. No value is committed by code 99.
            self._post_command(cfg['page'], cfg['command'], 99)
            if Decimal(self._editor_value(cfg)) != Decimal(before['value']):
                raise PzpError('Hodnota se mezitím změnila. Opakujte volbu z aktuálního stavu.')
            # One request per key. Lost replies abort the edit before Enter.
            try:
                self._post_command(cfg['editor'], cfg['command'], 13)
                if self._editor_value(cfg) not in ('', '0', '0.0'):
                    raise PzpError('Editor nebyl vymazán; změna se neuloží.')
                for char in text:
                    key = 10 if char == '-' else 11 if char == '.' else int(char)
                    self._post_command(cfg['editor'], cfg['command'], key)
                    self._editor_value(cfg)  # Revalidate editor identity after every key.
                if Decimal(self._editor_value(cfg)) != desired:
                    raise PzpError('Číslo v editoru neodpovídá požadavku; změna se neuloží.')
                current = self._parameter_value(cfg, self._read_page(cfg['page']))
                if current != before:
                    raise PzpError('Parametr se mezitím změnil; změna se neuloží.')
            except (PzpError, InvalidOperation):
                raise PzpError('Úprava nebyla dokončena. Potvrzení nové hodnoty nebylo odesláno.') from None
            try:
                self._post_command(cfg['editor'], cfg['command'], 14)
            except PzpError:
                pass  # Read back, never repeat Enter after a lost response.
            for attempt in range(4):
                time.sleep(.5)
                try:
                    actual = self._parameter_value(cfg, self._read_page(cfg['page']))
                    if Decimal(actual['value']) == desired:
                        return actual['value']
                except (PzpError, InvalidOperation):
                    break
            raise WriteUncertain('Regulátor nepotvrdil požadovanou hodnotu. Příkaz se neopakuje; načtěte aktuální stav.')

    def cycle_parameter(self, code):
        cfg = self.catalog[code]
        if cfg['kind'] not in ('cycle', 'boolean'):
            raise ValueError('Parametr nemá přepínání stavů.')
        with self._lock:
            before = self._parameter_value(cfg, self._read_page(cfg['page']))
            if not before['available']:
                raise PzpError('Regulátor tuto volbu nyní nenabízí.')
            try:
                self._post_command(cfg['page'], cfg['command'], 99)
            except PzpError:
                pass
            time.sleep(.6)
            after = self._parameter_value(cfg, self._read_page(cfg['page']))
            if after['value'] == before['value']:
                raise WriteUncertain('Změna nebyla potvrzena. Příkaz se automaticky neopakuje.')
            return after['value']

    def set_boolean(self, code, desired):
        cfg = self.catalog[code]
        if cfg['kind'] != 'boolean':
            raise ValueError('Parametr nemá hodnoty Ano/Ne.')
        with self._lock:
            before = self._parameter_value(cfg, self._read_page(cfg['page']))
            if before['value'] not in ('Ano','Ne'):
                raise UnsupportedFirmware('Neznámá hodnota přepínače')
            if (before['value'] == 'Ano') == desired:
                return before['value']
            return self.cycle_parameter(code)

    def _schedule_state(self, code):
        cfg = SCHEDULES[code]
        root = self._read_page(cfg['page'])
        access = root.find('ACCESS')
        inputs = root.findall('INPUT')
        if access is None or access.get('UCID') != cfg['version'] or len(inputs) != 18:
            raise UnsupportedFirmware('Změnilo se rozložení časového programu.')
        values = [n.get('VALUE','') for n in inputs]
        if (not all(re.fullmatch(r'\d{2}:\d{2}', s) for s in values[2:5])
                or not all(s in ('0','1') for s in values[5:17])):
            raise UnsupportedFirmware('Neznámý formát časového programu.')
        return {'program':code, 'name':values[1], 'available':values[0]=='1',
                'day':values[17], 'start':values[2],
                'slots':[s=='1' for s in values[5:17]],
                '_symbols':[n.get('NAME') for n in inputs[5:17]]}

    def schedule(self, data):
        code = data['program']
        if code not in SCHEDULES:
            raise ValueError('Neznámý časový program.')
        cfg = SCHEDULES[code]
        action = data.get('action','view')
        with self._lock:
            if action in ('day_view','day_set'):
                return self._schedule_day(data)
            state = self._schedule_state(code)
            if action in SCHEDULE_NAVIGATION:
                if not state['available']:
                    raise PzpError('Časový program není dostupný.')
                # Navigation changes only the editor viewport, never schedule bits.
                self._post_command(cfg['page'], cfg['command'], SCHEDULE_NAVIGATION[action])
                state = self._schedule_state(code)
            elif action == 'set':
                if not state['available']:
                    raise PzpError('Časový program není dostupný.')
                slot = data.get('slot')
                desired = data.get('value')
                if type(slot) is not int or not 0 <= slot < 12 or type(desired) is not bool:
                    raise ValueError('Neplatný časový interval.')
                if (state['day'] != data.get('day') or state['start'] != data.get('start')
                        or state['slots'] != data.get('expected_slots')):
                    raise PzpError('Zobrazení programu se mezitím změnilo. Obnovte kartu a opakujte volbu.')
                if state['slots'][slot] != desired:
                    try:
                        self._post_command(cfg['page'], state['_symbols'][slot], int(desired))
                    except PzpError:
                        raise WriteUncertain('Spojení se přerušilo při změně programu. Nic se neopakuje; obnovte zobrazení.') from None
                    prepared = self._schedule_state(code)
                    expected = list(state['slots']);expected[slot] = desired
                    if (prepared['day'] != state['day'] or prepared['start'] != state['start']
                            or prepared['slots'] != expected):
                        raise WriteUncertain('Časový program nepotvrdil očekávanou změnu.')
                    try:
                        # The original UI sends command 5 when leaving the editor.
                        self._post_command(cfg['page'], cfg['command'], 5)
                    except PzpError:
                        raise WriteUncertain('Potvrzení programu nelze ověřit. Příkaz se neopakuje.') from None
                    state = self._schedule_state(code)
                    if state['day'] == data['day'] and state['start'] == data['start']:
                        if state['slots'][slot] != desired:
                            raise WriteUncertain('Regulátor nepotvrdil uložení programu.')
                    else:
                        raise WriteUncertain('Editor se po potvrzení přesunul. Obnovte zvolený den a ověřte program.')
            elif action != 'view':
                raise ValueError('Neznámá akce programu.')
            return {k:v for k,v in state.items() if not k.startswith('_')}

    def _schedule_position(self, code, day, start):
        cfg=SCHEDULES[code]
        state=self._schedule_state(code)
        for _ in range(25):
            if state['day']!=day or not state['available']:
                raise PzpError('Zvolený den se mezitím změnil. Obnovte program.')
            if state['start']==start:return state
            command=3 if state['start']>start else 4
            self._post_command(cfg['page'],cfg['command'],command)
            updated=self._schedule_state(code)
            if updated['start']==state['start']:break
            state=updated
        raise PzpError('Nelze nastavit zvolený čas programu.')

    def _read_schedule_day(self, code, day):
        slots=[]
        for hour in range(0,24,3):
            slots.extend(self._schedule_position(code,day,f'{hour:02}:00')['slots'])
        return slots

    def _schedule_day(self, data):
        code=data['program'];cfg=SCHEDULES[code]
        initial=self._schedule_state(code);day=initial['day'];start=initial['start']
        if not initial['available']:raise PzpError('Program nyní není dostupný.')
        if data.get('day')!=day or data.get('start')!=start:
            raise PzpError('Zobrazený den nebo čas se změnil. Obnovte kartu.')
        try:
            current=self._read_schedule_day(code,day)
            if data['action']=='day_set':
                desired=data.get('day_slots');expected=data.get('expected_day_slots')
                if (not isinstance(desired,list) or len(desired)!=96 or any(type(v)is not bool for v in desired)
                        or current!=expected):
                    raise PzpError('Program dne se mezitím změnil nebo má neplatný formát. Načtěte jej znovu.')
                for hour in range(0,24,3):
                    state=self._schedule_position(code,day,f'{hour:02}:00')
                    offset=hour*4;old=current[offset:offset+12];new=desired[offset:offset+12]
                    if state['slots']!=old:raise WriteUncertain('Program byl souběžně změněn. Část úprav již mohla být uložena; nic se neopakuje.')
                    if old==new:continue
                    for i,value in enumerate(new):
                        if old[i]==value:continue
                        try:self._post_command(cfg['page'],state['_symbols'][i],int(value))
                        except PzpError:raise WriteUncertain('Spojení se přerušilo. Část programu již mohla být změněna; nic se neopakuje.') from None
                        old=list(old);old[i]=value
                        check=self._schedule_state(code)
                        if check['day']!=day or check['start']!=state['start'] or check['slots']!=old:
                            raise WriteUncertain('Regulátor nepotvrdil připravený program. Nic se neopakuje.')
                    try:self._post_command(cfg['page'],cfg['command'],5)
                    except PzpError:raise WriteUncertain('Potvrzení programu se ztratilo. Obnovte skutečný program; příkaz se neopakuje.') from None
                current=self._read_schedule_day(code,day)
                if current!=desired:raise WriteUncertain('Celý den nebyl ověřen. Načtěte skutečný stav programu.')
            state=self._schedule_position(code,day,start)
            return {**{k:v for k,v in state.items() if not k.startswith('_')},'day_slots':current}
        finally:
            # Navigation only, never replay a settings write after a failure.
            try:self._schedule_position(code,day,start)
            except PzpError:pass

    def _history_detail(self):
        root = self._read_page('/PAGE323.XML')
        access = root.find('ACCESS')
        values = [n.get('VALUE','') for n in root.findall('INPUT')]
        if access is None or access.get('UCID') != '1642510284' or len(values) != 40:
            raise UnsupportedFirmware('Neznámé rozložení historie událostí.')
        # Bxx labels and availability flags come from the actual detail page XSL.
        positions = [('B01',6,7),('B02',9,10),('B03',11,12),('B04',13,14),
                     ('B07',15,16),('B08',17,18),('B10',19,20),('B11',21,22),
                     ('B12',23,24),('B13',25,26),('B14',27,28),('B16',29,30),
                     ('B17',31,32),('B18',33,34),('B19',35,36)]
        return {'available':values[1]=='1','description':values[2], 'time':values[3],
                'active':values[4]=='1', 'alarm':values[5]=='1',
                'temperatures':{name:values[index] for name,flag,index in positions if values[flag]=='1'},
                'has_older':values[38]=='1','has_newer':values[39]=='1'}

    def history(self, data):
        action=data.get('action','view')
        if action not in ('view','newest','older','newer'):
            raise ValueError('Neznámá akce historie.')
        with self._lock:
            state=self._history_detail()  # Validate the firmware before navigation.
            command='__T5C887235_USINT_u'
            if action=='newest':
                self._post_command('/PAGE16.XML',command,20)
                page=self._read_page('/PAGE322.XML')
                access=page.find('ACCESS')
                if access is None or access.get('UCID')!='1642510283':
                    raise UnsupportedFirmware('Neznámé rozložení seznamu historie.')
                self._post_command('/PAGE322.XML',command,1)
                state=self._history_detail()
            elif action in ('older','newer'):
                if not state['has_'+action]:
                    return state
                self._post_command('/PAGE323.XML',command,23 if action=='older' else 22)
                state=self._history_detail()
            return state

    def _admin_values(self, cfg, *, editor=False):
        prefix = 'editor_' if editor else ''
        root = self._read_page(cfg['editor'] if editor else cfg['page'])
        access = root.find('ACCESS')
        nodes = root.findall('INPUT')
        if (access is None or access.get('UCID') != cfg[prefix+'version']
                or [n.get('NAME') for n in nodes] != cfg[prefix+'symbols']):
            raise UnsupportedFirmware('Změnilo se rozložení nastavení. Zápis je zakázán.')
        values = [n.get('VALUE', '') for n in nodes]
        if editor and (len(values)<2 or not values[1] or not values[1].startswith(cfg.get('title_prefix',''))):
            raise UnsupportedFirmware('Editor neodpovídá zvolenému nastavení.')
        return values

    def _admin_token(self, section, values, *, field=None, original=None):
        now=time.monotonic()
        self._admin_tokens={k:v for k,v in self._admin_tokens.items() if now-v['time']<900}
        while len(self._admin_tokens)>24:
            self._admin_tokens.pop(next(iter(self._admin_tokens)))
        token=secrets.token_urlsafe(24)
        self._admin_tokens[token]={'section':section,'values':values,'field':field,
                                   'original':original,'time':now}
        return token

    @staticmethod
    def _admin_available(field, values):
        blocked=field.get('blocked_index')
        if blocked is not None and values[blocked]!='0':return False
        i=field.get('visible')
        return i is None or values[i]!='0'

    @staticmethod
    def _admin_value(field, values):
        if field.get('language'):
            return 'Čeština' if values[1]=='1' else 'Deutsch'
        if field.get('format')=='hex':
            return ''.join(values[i].upper() for i in field['indices'])
        value=field.get('join',' ').join(values[i] for i in field['indices'])
        if field['kind']=='bool': return value=='1'
        if field['kind']=='choice':
            return next((k for k,v in field['options'].items() if str(v)==value),value)
        return value

    def admin_view(self, section):
        with self._lock:
            if section not in self.admin_catalog:raise ValueError('Neznámá část nastavení.')
            cfg=self.admin_catalog[section]
            values=self._admin_values(cfg)
            fields=[]
            for f in cfg['fields']:
                item={k:f[k] for k in ('key','label','kind','secret','options','max','confirm') if k in f}
                item['available']=self._admin_available(f,values)
                item['value']=bool(self._admin_value(f,values)) if f.get('secret') else self._admin_value(f,values)
                fields.append(item)
            return {'section':section,'name':cfg['name'],'note':cfg['note'],'fields':fields,
                    'confirm':cfg.get('confirm'),'host':self.host,
                    'token':self._admin_token(section,values)}

    def _admin_editor_response(self, section, f, values, original):
        return {'section':section,'editor':f['key'],'name':f['label'],
                'values':(['••••'] if f.get('secret') else
                          [{'label':f.get('editor_labels',[])[i] if f.get('editor_labels') else '',
                            'value':v} for i,v in enumerate(values) if i!=1 and (f.get('editor_labels') or i==0)]),
                'secret':f.get('secret',False),'keys':f['key_labels'],
                'token':self._admin_token(section,values,field=f['key'],original=original)}

    def admin_action(self, data):
        """Allowlisted actions only; credentials never enter HA service events/states."""
        section=data.get('section')
        with self._lock:
            if section not in self.admin_catalog:raise ValueError('Neznámé nastavení.')
            cfg=self.admin_catalog[section]
            token=data.get('token','')
            snapshot=self._admin_tokens.pop(token,None)  # Consume even on failure; no replay.
            if not snapshot or snapshot['section']!=section or time.monotonic()-snapshot['time']>900:
                raise PzpError('Zobrazení vypršelo. Načtěte aktuální nastavení.')
            fields={f['key']:f for f in cfg['fields']}
            action=data.get('action')
            before=self._admin_values(cfg)
            if action=='form':
                changes=data.get('changes')
                if not isinstance(changes,dict) or not changes:raise ValueError('Nejsou zadané změny.')
                payload={}
                for key,value in changes.items():
                    f=fields.get(key)
                    if not f or f['kind']!='form' or not self._admin_available(f,before):
                        raise PzpError('Toto pole regulátor nyní nenabízí.')
                    if not isinstance(value,str) or len(value.encode('utf-8'))>f['max'] or any(ord(c)<32 for c in value):
                        raise ValueError('Text je příliš dlouhý nebo obsahuje řídicí znaky.')
                    if section=='credentials' and not value:raise ValueError('Přihlašovací údaje nesmí být prázdné.')
                    i=f['indices'][0]
                    if before[i]!=snapshot['values'][i]:raise PzpError('Nastavení se mezitím změnilo. Obnovte jej.')
                    if value!=before[i]:payload[cfg['symbols'][i]]=value
                if not payload:return self.admin_view(section)
                if cfg.get('commit'):payload[cfg['commit']]='1'
                encoded=urllib.parse.urlencode(payload,quote_via=urllib.parse.quote,safe="~()*!.'-").encode()+b'&'
                try:
                    url,body=self._request(cfg['page'],encoded)
                    if self._is_login(url,body):self._logged_in=False
                except PzpError:pass  # Read only after the single write.
                if section=='credentials':
                    username=changes.get('username',self.username);password=changes.get('password',self._password)
                    candidate=PzpClient(self.host,username,password,timeout=self.timeout)
                    try:candidate.read_state()
                    except PzpError:
                        raise WriteUncertain('Nové přihlášení nelze ověřit. Nic se neopakuje. Použijte formulář Obnovit připojení HA.') from None
                    self.username=username;self._password=password;self._logged_in=False
                    try:result=self.admin_view(section)
                    except PzpError:result={'message':'Nové přihlášení ověřeno. Pro načtení nastavení stiskněte Načíst.'}
                    result['_credentials']={'username':username,'password':password}
                    return result
                after=self._admin_values(cfg)
                if any(after[fields[k]['indices'][0]]!=v for k,v in changes.items()):
                    raise WriteUncertain('Regulátor nepotvrdil uložené hodnoty. Změna se neopakuje.')
                return self.admin_view(section)
            key=data.get('field');f=fields.get(key)
            if not f or not self._admin_available(f,before):raise PzpError('Tuto volbu regulátor nyní nenabízí.')
            if action in ('open','set','pulse','cycle') and key!='clock':
                if any(before[i]!=snapshot['values'][i] for i in f['indices']):
                    raise PzpError('Hodnota se mezitím změnila. Obnovte nastavení.')
            if action=='open' and f['kind']=='editor':
                self._post_command(cfg['page'],f['command'],99)
                values=self._admin_values(f,editor=True)
                return self._admin_editor_response(section,f,values,before)
            if action in ('key','commit') and f['kind']=='editor':
                if snapshot['field']!=key:raise PzpError('Nesouhlasí otevřený editor.')
                values=self._admin_values(f,editor=True)
                if values!=snapshot['values'] or (key!='clock' and any(before[i]!=snapshot['original'][i] for i in f['indices'])):
                    raise PzpError('Editor nebo hodnota se mezitím změnily. Změna se neuloží.')
                command=14 if action=='commit' else data.get('key')
                if type(command) is not int or command not in f['keys'] or (action=='key' and command==14):
                    raise ValueError('Neplatná klávesa editoru.')
                if action=='key':
                    try:self._post_command(f['editor'],f['command'],command)
                    except PzpError:
                        raise WriteUncertain('Odpověď editoru se ztratila. Hodnota nebyla potvrzena; otevřete editor znovu.') from None
                    return self._admin_editor_response(section,f,self._admin_values(f,editor=True),snapshot['original'])
                try:self._post_command(f['editor'],f['command'],14)
                except PzpError:pass
                time.sleep(.3)
                after=self._admin_values(cfg)
                expected=values[0]
                actual=self._admin_value(f,after)
                if f['editor']=='/PAGE388.XML':
                    expected=f'{int(values[4]):02}.{int(values[5]):02}.{int(values[6]):04} {int(values[0]):02}:{int(values[2]):02}'
                elif f['editor']=='/PAGE389.XML':expected=f'{int(values[0]):02}:{int(values[2]):02}'
                elif f['editor']=='/PAGE337.XML':expected=f'{int(values[0]):02}:{int(values[2]):02}:{int(values[3]):02}'
                elif f.get('format')=='numeric':
                    try:expected=Decimal(expected);actual=Decimal(actual)
                    except InvalidOperation:raise WriteUncertain('Neznámý formát potvrzené hodnoty.') from None
                elif f.get('format')=='hex':
                    try:expected=int(expected,16);actual=int(actual,16)
                    except ValueError:raise WriteUncertain('Neznámý formát CIB adresy.') from None
                elif f.get('format')=='ip':
                    try:expected=tuple(map(int,expected.split('.')));actual=tuple(map(int,actual.split('.')))
                    except ValueError:raise WriteUncertain('Neznámý formát síťové adresy.') from None
                if actual!=expected:
                    raise WriteUncertain('Uložení nelze potvrdit. Příkaz se neopakuje; načtěte skutečnou hodnotu.')
                return self.admin_view(section)
            if action=='set' and f['kind'] in ('bool','choice'):
                desired=data.get('value')
                if f['kind']=='bool':
                    if type(desired) is not bool:raise ValueError('Očekávána volba Ano/Ne.')
                    value=int(desired);symbol=cfg['symbols'][f['indices'][0]]
                else:
                    if desired not in f['options']:raise ValueError('Neplatná volba.')
                    value=f['options'][desired];symbol=f['command']
                if self._admin_value(f,before)==desired:return self.admin_view(section)
                try:self._post_command(cfg['page'],symbol,value)
                except PzpError:pass
                time.sleep(.3)
                after=self._admin_values(cfg)
                if self._admin_value(f,after)!=desired:raise WriteUncertain('Změna nebyla potvrzena. Neopakuje se.')
                return self.admin_view(section)
            if (action=='pulse' and f['kind']=='pulse') or (action=='cycle' and f['kind']=='cycle'):
                symbol=f.get('command',cfg['symbols'][f['indices'][0]])
                value=99 if action=='cycle' else int(before[f['indices'][0]]=='0')
                try:self._post_command(cfg['page'],symbol,value)
                except PzpError:raise WriteUncertain('Odpověď na příkaz se ztratila. Příkaz se neopakuje.') from None
                result=self.admin_view(section)
                result['message']='Příkaz přijat, zobrazen aktuální stav regulátoru.'
                return result
            raise ValueError('Neplatná akce nastavení.')


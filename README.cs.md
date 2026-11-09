# Tepelná čerpadla PZP v Home Assistantu

**Komunitní beta 0.5.0b1 · místní komunikace · Home Assistant 2025.10.1 a novější**

Integrace vznikla pro **HP 3 AWX 10 ECONOMIC s regulátorem SW 05.03.00**. U tohoto modelu vychází z provozní integrace 0.4.1. Podpora jiných modelů a verzí firmware zatím není ověřená. Nejde o oficiální produkt PZP. Neznámé rozložení stránky nebo odlišný symbol parametru se odmítne; úspěšné připojení samo nepotvrzuje všechny funkce.

## Co umí

- Sezóna H111, režim H110, 24 číselných parametrů, F005 a F100 podle dostupnosti regulátoru.
- Časové programy topení, směšovače, TUV a cirkulace; čtvrthodiny, kopírování a vyplnění dne se zpětnou kontrolou.
- Historie událostí a teplot při události.
- Správcovská karta se 12 oblastmi nativního nastavení. Hesla a klíče nezobrazuje jako text a nevytváří z nich entity.
- Volitelné [Modbus soubory](examples/modbus/README.md) pro teploty, stavy a diagnostiku.

Podrobně rozlišujeme implementované a skutečně vyzkoušené funkce v [COVERAGE.cs.md](COVERAGE.cs.md). Číselné parametry jsou textová pole, protože pro všechny nemáme ověřené povolené meze. Hodnoty je potřeba volit podle dokumentace konkrétního čerpadla.

## Instalace

1. V HACS přidejte **vlastní repozitář** `https://github.com/PetrMlejnek/home-assistant-pzp`, typ **Integration**. V hlavním katalogu projekt zatím není.
2. Povolte předběžná vydání, vyberte `0.5.0b1`, stáhněte a restartujte HA.
3. V **Nastavení → Zařízení a služby → Přidat integraci** vyhledejte **PZP Heat Pump**.
4. Vyplňte vlastní IPv4 adresu nebo DNS jméno čerpadla, případně s portem, a přihlášení do jeho webu. Bez `http://` a bez cesty. Výchozí port je 80; IPv6 tato beta nepodporuje.

Při ruční instalaci zkopírujte jen složku `custom_components/pzp_web` do stejné cesty v konfiguraci HA. Přihlášení zůstává v konfigurační položce HA. Integrace nevyhledává čerpadlo v síti a nenastavuje router. Vlastní DHCP rezervace pomáhá udržet adresu stabilní.

## Panel

V **Nastavení → Nástěnky → Zdroje** přidejte tři zdroje typu **JavaScript modul** (může být potřeba rozšířený režim profilu):

```text
/pzp_web/static/pzp-schedule-card.js?v=0.5.0b1
/pzp_web/static/pzp-history-card.js?v=0.5.0b1
/pzp_web/static/pzp-admin-card.js?v=0.5.0b1
```

Do editoru surové konfigurace prázdné nástěnky vložte [examples/dashboard.yaml](examples/dashboard.yaml). Pokud se vaše entita **Volba sezóny** nejmenuje `select.pzp_volba_sezony`, nahraďte tento název v celém příkladu. Karty si podle ní najdou správnou integrační položku. Původní volba `config_entry_id` také funguje; je užitečná i pro obnovení připojení, pokud se entita nenačte. ID najdete v URL detailu integrace nebo v atributu entity při funkčním spojení.

Při přechodu ze soukromé 0.4.1 nejdříve odstraňte původní zdroje `/local/pzp-…`; stejné karty nesmí být načtené dvakrát. Zachovejte existující integrační položku a vlastní názvy entit. Modbus YAML ani domácí panel nepřepisujte obecnými příklady. Při dalších aktualizacích změňte parametr `?v=` a obnovte prohlížeč. HACS aktualizuje integraci a přibalené karty, nikoli samostatný panel a Modbus příklady.

## Provoz

Regulaci stále vykonává čerpadlo. Instalace, načítání, obnovení spojení ani vypnutí HA neposílají provozní nastavení. Integrace nepřebírá nadřazené řízení WR50xxx a neobchází ochrany. Neověřený zápis automaticky neopakuje. Při přerušené úpravě celého dne může zůstat uložená jen část; před další změnou program znovu načtěte.

Správcovské API kontroluje oprávnění i na serveru. Běžné entity a akce programů/historie používají standardní oprávnění HA. Web regulátoru komunikuje po místním HTTP. Žádná cloudová mezivrstva ani telemetrie integrace není potřeba.

Úpravy LAN mohou přerušit spojení. Obnovení webového připojení nemění adresu Modbusu ani router. Změny sítě, účtu, SMTP a všech podmíněných funkcí nebyly kompletně vyzkoušeny na zařízení. Fyzický výpadek napájení a Wi-Fi nebyl testován. Samostatná webová integrace obsluhuje právě ověřené webové rozhraní; Modbus příklady mají vlastní rozsah a předpoklady.

## Další modely a hlášení chyb

Do GitHub issue napište model, verzi regulátoru, verzi HA, kód parametru a očištěnou chybu. Nepřikládejte přístupové údaje, celé stránky regulátoru, soubory `.storage`, zálohy nebo identifikátory domácnosti. Údaje pro další firmware nejprve ověřujeme při čtení; neznámé symboly a rozsahy se nedoplňují odhadem.

Zdrojové kódy jsou pod licencí MIT. Dokumenty a firmware výrobce nejsou součástí repozitáře. Aktuální veřejná beta není automaticky nasazena do původního domácího HA.

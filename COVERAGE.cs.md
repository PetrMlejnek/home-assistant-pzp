# Pokrytí webu PZP

Základ 0.4.1, veřejná beta 0.5.0b1, regulátor SW 05.03.00. Převod uživatelské úrovně; nikoli zpřístupnění servisních oprávnění výrobce.

| Oblast | Implementace v HA |
|---|---|
| Sezóna a režim období | H110, H111, H112, H113 |
| TUV | O001, O010, O020, O039 |
| Topný okruh | R040, R043, R045, R046, R050, R051, R080, H740 |
| Směšovač | M140, M143, M145, M146, M150, M151 |
| Provoz a blokování | U000, C001, C003, C020 |
| Poruchové chování | F005, F100; nativní editory F101 a chráněného F115 podle dostupnosti |
| Pokojové terminály 1–4 | CIB adresa, komfort/útlum topení, komfort chlazení, skutečná teplota |
| Čtyři programy | Čtvrthodiny, kopie/vložení dne, zapnutí/vypnutí dne, kontrola všech 96 intervalů |
| Historie | Listování událostmi a uložené teploty Bxx |
| Jazyk | Čeština / němčina; známé lokalizované stavy přeloženy pro integraci |
| Hodiny | Datum, čas, UTC pásmo, automatická změna letního času |
| LAN | IP, maska, brána, DNS, DHCP, načtení aktuálního nastavení, uložení |
| Počasí | Stav služby, město, země, chráněný API klíč |
| E-mail | Příjemci, SMTP, autentizace, účet, heslo, automatické nastavení, zapnutí, jazyk, explicitní test |
| Vzdálená služba PZP | Diagnostika a reset U050; nejde o povolení nového vzdáleného přístupu |
| Přihlášení čerpadla | Změna účtu s ověřením nového přihlášení a převzetím do HA |
| Obnova připojení HA | Ověření hostu a údajů před uložením; pouze webová integrace |
| Stavy a informace | Volitelné Modbus YAML v examples/modbus; nejsou instalovány webovou integrací |

Karta Nastavení obsahuje 12 oblastí a 63 položek včetně informačních polí. Přístup správce se kontroluje v kartě i serverovém API. Hesla, API klíče a PIN se nevracejí jako otevřený text; nejsou entitami ani událostmi služeb HA.

## Přesné hranice

- Skryté volby zůstávají zakázané. F100/F101/F115 a nepřipojené terminály nebyly aktivovány za účelem zkoušky. Struktura editorů je ověřena z původního XML/XSL/JS, provozní zápisy do skrytých parametrů nejsou živě vyzkoušené.
- Servisní/instalační oprávnění, bezpečnostní ochrany a nadřazené WR50xxx nejsou obcházeny. Hromadné úpravy mají výslovný rozsah jednoho dne; nativní ikony s neověřeným rozsahem nebyly slepě přebírány.
- Při instalaci se neměnilo přihlášení, síť, SMTP, příjemci ani API klíče. Nebyl odeslán testovací e-mail ani resetována vzdálená služba. Tyto operace jsou připraveny pro výslovnou volbu uživatele, ale jejich skutečné změny na dálku nebyly testovány.
- Obnova webového připojení HA neupravuje Modbus YAML ani router. Při budoucí změně IP je nutné upravit také Modbus.
- Žádné zápisy při startu, obnovení Wi-Fi či vypnutí HA; žádný heartbeat ani automatické opakování neověřeného zápisu. Při přerušené hromadné úpravě může být uložena část dne; nejprve znovu načíst skutečný program.
- Fyzické odpojení Wi-Fi a napájení nebylo testováno. Nezávislost místní regulace neznamená ochranu před poruchou samotného čerpadla.

# Volitelné Modbus příklady / Optional Modbus examples

These files are separate from the HACS web integration. They target one PZP controller, unit 1, protocol 03.03, verified on software 05.03.00. They are not automatically installed. They contain read sensors **and explicit user controls**, including standby, local operating flags and a fault-reset button. They do not enable supervisory WR50xxx control. Keep existing working YAML instead of installing a duplicate hub.

Čtyři kroky pro novou instalaci:

1. Ověřte model a Modbus protokol svého regulátoru. Zálohujte konfiguraci HA. Zkopírujte tři soubory `pzp_modbus.yaml`, `pzp_template.yaml`, `pzp_customize.yaml` do konfigurace HA.
2. Do svého **secrets.yaml** doplňte `pzp_host: VLASTNI_IP_CERPADLA`. Hodnota je pouze adresa zařízení, bez URL. Do veřejného repozitáře tento soubor neukládejte.
3. Sloučte níže uvedené klíče s existující konfigurací. YAML klíče `modbus`, `template` a `homeassistant` nesmí být duplicitní; pokud je už máte, začleňte obsah podle své stávající struktury.
4. Zkontrolujte konfiguraci v HA, restartujte a ověřte změny `sensor.pzp_hodiny_raw` a `binary_sensor.pzp_zive_spojeni`, skutečné teploty a použité sondy. Ovládání zkoušejte až po ověření správného zařízení a registrů.

```yaml
modbus: !include pzp_modbus.yaml
template: !include pzp_template.yaml
homeassistant:
  customize: !include pzp_customize.yaml
```

The files use the `pzp_hp` hub and fixed `pzp_…` entity names and unique IDs. Adapt **all** references for multiple pumps or renamed/colliding entities. A fresh installation can assign different entity IDs if names already exist. The `_1`, `_2`, etc. in block sensors also describe generated slave-count entities; do not globally remove these suffixes.

Čas hodin regulátoru se čte každých 60 sekund, dostupnost sleduje jeho změnu s mezí 180 sekund. Nepoužité sondy jsou nedostupné podle příznaků regulátoru. Tyto příklady nepředstavují plnou automatickou detekci možností jiného modelu.

Changing the web integration host does not change `pzp_host` and vice versa. Do not expose Modbus TCP port 502 to the internet. Home Assistant's Modbus implementation determines transport retries; the web client's no-replay guarantee does not apply to this separate core integration.

# PZP Heat Pump for Home Assistant

[Český návod](README.cs.md) · [Coverage](COVERAGE.cs.md) · [Modbus examples](examples/modbus/README.md)

**0.5.0b1 · community beta · local polling · Home Assistant 2025.10.1+**

Local settings, schedules and event history for PZP heat pumps using the verified Teco/SoftPLC web interface. This is an independent community project, not an official PZP product.

The original implementation was used with **PZP HP 3 AWX 10 ECONOMIC, controller software 05.03.00**. Other models and firmware versions have **not** been verified. The integration checks page versions and parameter identities and refuses incompatible operations. Matching one page does not establish compatibility with every function.

## Features

- Local heating season, changeover mode, 24 numeric parameters and additional switches.
- Four quarter-hour schedules: heating, mixer, hot water and circulation; copy or fill one day with readback of all 96 slots.
- Controller event history and temperatures captured at each event.
- An administrator card for the verified native settings, with write-only secret fields.
- Optional Modbus YAML for live temperatures, status and diagnostics. Modbus is a separate, explicitly installed configuration, not a built-in part of the web integration.

The supplied cards and parameter names are currently in Czech. Setup is available in English and Czech. Numeric parameters use text entities because the verified protocol does not expose trustworthy min/max bounds for every field.

## Installation through HACS

This repository is **not in the default catalog**. Add `https://github.com/PetrMlejnek/home-assistant-pzp` as a **custom repository**, category **Integration**. Enable prerelease versions to select `0.5.0b1`, download it, and restart Home Assistant.

Then open **Settings → Devices & services → Add integration → PZP Heat Pump**. Enter the heat pump's local IPv4 address or DNS name (optional `:port`), and the account used by its own web interface. Do not enter a URL or path. The default port is 80. IPv6 authorities are not supported in this beta.

The integration does not discover devices or change router settings. Assigning a DHCP reservation in your router avoids address changes. Credentials are stored only in the Home Assistant config entry; protect your HA backups accordingly.

For manual installation, copy `custom_components/pzp_web` into your HA `config/custom_components` directory, then restart and add the integration. A release ZIP contains this directory plus documentation and examples; do not copy the whole repository into `custom_components`.

## Dashboard cards

The three cards and their shared module are delivered inside the integration. In **Settings → Dashboards → Resources** (advanced mode), add these three **JavaScript module** resources:

```text
/pzp_web/static/pzp-schedule-card.js?v=0.5.0b1
/pzp_web/static/pzp-history-card.js?v=0.5.0b1
/pzp_web/static/pzp-admin-card.js?v=0.5.0b1
```

Create an empty dashboard and paste [examples/dashboard.yaml](examples/dashboard.yaml) into its raw configuration editor. The example uses `select.pzp_volba_sezony`; replace it throughout with the actual **Volba sezóny** entity belonging to your heat pump if its ID differs. Each card resolves the config entry from that entity. Multiple web entries can be routed explicitly, but simultaneous use with multiple physical pumps has not been tested. The Modbus examples use a single fixed entity namespace and require adaptation for a second pump.

For an older dashboard, the explicit `config_entry_id` option remains supported. It also allows the administrator recovery form to work when the season entity is not loaded. Find the ID in the integration detail URL or the entity's `config_entry_id` attribute while it is loaded. It is an identifier, not a password.

Do not load both an old `/local/pzp-…` card and the new resource for the same card. Remove the old resource first, then reload the browser. On future upgrades, change the `?v=` value and reload. Dashboard and optional YAML files are maintained separately from HACS updates.

## Behavior and limitations

Setup, polling, reconnect and HA shutdown do not write controller settings. Plant regulation and schedules remain in the controller. No supervisory WR50xxx mode, heartbeat override, direct compressor control or safety-interlock bypass is used. A request whose outcome is uncertain is never automatically replayed. A partially completed day edit can leave part of that day changed: reload its actual contents before another edit.

The administrator API checks HA administrator rights on the server and uses non-cacheable responses. Ordinary entities and schedule/history actions use HA's normal permissions. Network, account, SMTP and optional protected settings have **not** all been exercised on hardware. Follow [the exact coverage notes](COVERAGE.cs.md). Changing device network settings may disconnect it; changing the web connection does not update Modbus or the router.

The native controller interface uses HTTP on the local network. There is no cloud relay or telemetry in this integration. An existing controller weather or mail service remains the controller's own feature. Physical power-loss and Wi-Fi-disconnection tests have not been performed.

## Existing private 0.4.1 installations

Back up your HA configuration first. Keep the existing config entry; do not delete and recreate it. The domain `pzp_web`, unique ID scheme and existing entity IDs are retained. Replace only the integration directory, restart, and update the card resources as above. Keep your current Modbus YAML, dashboard customizations and connection address. The generic examples are for a new installation and should not overwrite working household files.

This public beta was prepared separately; publishing it does not install it on the original household server.

## Development and support

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
node --test tests/cards.test.mjs
python scripts/validate_package.py
```

CI also runs hassfest, HACS validation and disposable real HA instances with a **simulated** controller. The beta passed on **HA 2025.10.1 / Python 3.13** and **HA 2026.11.1 / Python 3.14**: setup, duplicate detection, creation of all 29 entities, card routing metadata, stable entity IDs across reload, and unload. The historical HA test environment pins `pycares==4.11.0` for its older `aiodns`; this is a CI dependency constraint, not an integration requirement.

Unit and simulated integration tests do not prove new hardware compatibility. Report the model, controller firmware, HA version, relevant parameter code and a sanitized error. Do not post passwords, cookies, full config entries, raw controller pages or household exports. See [CONTRIBUTING.md](CONTRIBUTING.md).

MIT licensed. PZP and Teco names identify compatible equipment; their firmware and protocol documents are not distributed here.

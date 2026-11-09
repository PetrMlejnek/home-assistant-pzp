# Contributing

Report model, controller software, HA version, affected parameter code, expected behavior and a sanitized error. New firmware support requires evidence of page identity, visibility, native input format and readback semantics. Do not infer PLC symbols or bounds from nearby parameters.

Start with read-only compatibility checks. Keep tests synthetic. Never commit raw controller pages, session cookies, household IP/MAC addresses, serial numbers, account details, backups or protocol documents owned by someone else. Describe unsupported operations accurately rather than disabling compatibility guards.

Run the commands in README.md. CI uses a disposable Home Assistant with a simulated controller, not the contributor's heat pump. Live setup, polling, reconnect and unload must remain free of settings writes. An ambiguous command must not be replayed, including non-idempotent toggles. Preserve stored entity IDs when upgrading.

Use small changes with a description of the observed device behavior, tests, and remaining hardware limits. Contributions are provided under this repository's MIT license.

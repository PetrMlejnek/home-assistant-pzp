# PZP Heat Pump

- Public repository: publish only reusable source, synthetic tests and generic examples.
- Never add household addresses, identifiers, credentials, session data, live exports or backups.
- Keep credentials only in Home Assistant config entries.
- Do not guess PLC symbols, parameter bounds or firmware compatibility.
- Read before writing, verify afterwards, never retry an uncertain write or a toggle.
- Setup, reconnect, polling and shutdown must not write controller settings.
- Never enable supervisory overrides or bypass safety interlocks.
- Document verified coverage separately from intended coverage.
- Preserve existing unique IDs and entity IDs on upgrades.
- Run Python unit tests, JavaScript tests and package validation before a release.
- Do not deploy to a real heat pump or Home Assistant as part of repository maintenance without a separate user request.

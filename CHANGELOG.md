# Changelog

## 0.5.0b1 — 2026-11-09

First public beta based on the privately used 0.4.1 implementation.

- Removed household-specific addresses, identifiers and operational notes.
- Added HACS packaging, English/Czech installation guides and a reusable dashboard.
- Bundled all custom cards with the integration and added entity-based routing while retaining explicit config-entry IDs.
- Added normalized host input, duplicate-host checks and password selectors in setup.
- Preserved the domain, unique ID scheme, verified controller mappings, no-write lifecycle and no-replay behavior.
- Added optional separate Modbus examples; no automatic deployment or migration of a household's YAML.
- Added release artifact checks, frontend routing tests and CI with hassfest and simulated-controller HA smoke tests.

Hardware evidence remains limited to HP 3 AWX 10 ECONOMIC / SW 05.03.00. The public package changes have not yet been installed on physical equipment.

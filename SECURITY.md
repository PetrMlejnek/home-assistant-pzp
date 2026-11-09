# Security

Do not include credentials, cookies, raw controller responses, full Home Assistant backups or config entries in an issue. For a vulnerability involving authentication or secret disclosure, use GitHub's private vulnerability reporting if available, otherwise first open an issue requesting a private contact without exploit details or private data.

The integration talks to the configured controller on local HTTP. Its administrator endpoint requires an authenticated Home Assistant administrator and returns non-cacheable responses. Protect HA and its backups; the controller account is stored in the config entry. The source contains no shared credentials or hosted service.

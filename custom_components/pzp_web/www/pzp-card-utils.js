/* Route each card to its selected integration without household-specific IDs. */
export function entryReady(config, hass) {
  return Boolean(config?.config_entry_id ||
    (config?.entity && hass?.states?.[config.entity]?.attributes?.config_entry_id));
}

export function resolveEntryId(config, hass) {
  const id = config.config_entry_id || hass?.states?.[config.entity]?.attributes?.config_entry_id;
  if (typeof id !== 'string' || !id) {
    throw new Error('Vyberte entitu Volba sezóny této integrace, nebo zadejte config_entry_id.');
  }
  return id;
}

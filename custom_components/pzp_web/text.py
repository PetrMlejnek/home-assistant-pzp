"""Numeric keypad parameters; do not invent undocumented min/max bounds."""
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.exceptions import HomeAssistantError
from . import DOMAIN
from .client import PzpError
from .entity import PzpParameterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PzpNumericParameter(coordinator, entry, cfg)
        for cfg in coordinator.client.catalog.values() if cfg['kind'] == 'numeric'
    ])


class PzpNumericParameter(PzpParameterEntity, TextEntity):
    _attr_mode = TextMode.TEXT
    _attr_native_min = 1
    _attr_native_max = 9

    def __init__(self, coordinator, entry, cfg):
        super().__init__(coordinator, entry, cfg, 'text')
        self._attr_pattern = r'-?\d+(?:[.,]\d)?' if cfg['decimals'] else r'\d+'
        self._attr_icon = 'mdi:thermometer' if cfg['decimals'] else 'mdi:chart-bell-curve'
        if cfg['decimals']:
            self._attr_name += ' (°C)'

    @property
    def native_value(self):
        return self.parameter.get('value')

    async def async_set_value(self, value):
        try:
            await self.hass.async_add_executor_job(self.coordinator.client.set_numeric, self.cfg['code'], value)
        except (PzpError, ValueError) as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(str(err)) from None
        await self.coordinator.async_request_refresh()

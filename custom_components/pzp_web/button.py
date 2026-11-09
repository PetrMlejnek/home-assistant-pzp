"""Explicitly requested cycle command, never repeated automatically."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from . import DOMAIN
from .client import PzpError
from .entity import PzpParameterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PzpCycleParameter(coordinator, entry, cfg)
        for cfg in coordinator.client.catalog.values() if cfg['kind'] == 'cycle'
    ])


class PzpCycleParameter(PzpParameterEntity, ButtonEntity):
    _attr_icon = 'mdi:calendar-sync'

    def __init__(self, coordinator, entry, cfg):
        super().__init__(coordinator, entry, cfg, 'button')
        self._attr_name = 'PZP Změnit: ' + cfg['name']

    async def async_press(self):
        try:
            await self.hass.async_add_executor_job(self.coordinator.client.cycle_parameter, self.cfg['code'])
        except PzpError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(str(err)) from None
        await self.coordinator.async_request_refresh()

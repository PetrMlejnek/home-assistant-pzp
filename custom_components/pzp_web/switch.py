"""Additional local boolean parameters missing from the existing Modbus UI."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from . import DOMAIN
from .client import PzpError
from .entity import PzpParameterEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PzpBooleanParameter(coordinator, entry, cfg)
        for cfg in coordinator.client.catalog.values() if cfg['kind'] == 'boolean'
    ])


class PzpBooleanParameter(PzpParameterEntity, SwitchEntity):
    def __init__(self, coordinator, entry, cfg):
        super().__init__(coordinator, entry, cfg, 'switch')

    @property
    def is_on(self):
        return self.parameter.get('value') == 'Ano'

    async def _set(self, value):
        try:
            await self.hass.async_add_executor_job(self.coordinator.client.set_boolean, self.cfg['code'], value)
        except PzpError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(str(err)) from None
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)

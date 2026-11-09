"""PZP local settings, independent of the existing Modbus sensors."""
from datetime import timedelta
from pathlib import Path
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthError, PzpClient, PzpError, SCHEDULES, SCHEDULE_NAVIGATION
from .admin import PzpAdminView

DOMAIN = "pzp_web"
PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.TEXT, Platform.BUTTON, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    await hass.http.async_register_static_paths([
        StaticPathConfig('/pzp_web/static', str(Path(__file__).parent / 'www'), False)
    ])
    hass.http.register_view(PzpAdminView(hass))
    async def handle_history(call):
        coordinator = hass.data.get(DOMAIN, {}).get(call.data['config_entry_id'])
        if coordinator is None:
            raise HomeAssistantError('Integrace čerpadla není načtena.')
        try:
            result = await hass.async_add_executor_job(coordinator.client.history, dict(call.data))
        except (PzpError, ValueError) as err:
            raise HomeAssistantError(str(err)) from None
        return result if call.return_response else None

    async def handle_schedule(call):
        coordinator = hass.data.get(DOMAIN, {}).get(call.data['config_entry_id'])
        if coordinator is None:
            raise HomeAssistantError('Integrace čerpadla není načtena.')
        try:
            result = await hass.async_add_executor_job(coordinator.client.schedule, dict(call.data))
        except (PzpError, ValueError) as err:
            raise HomeAssistantError(str(err)) from None
        return result if call.return_response else None

    schema=vol.Schema({
        vol.Required('config_entry_id'): str,
        vol.Required('program'): vol.In(list(SCHEDULES)),
        vol.Optional('action', default='view'): vol.In(['view','set','day_view','day_set',*SCHEDULE_NAVIGATION]),
        vol.Optional('day'): str,
        vol.Optional('start'): str,
        vol.Optional('slot'): vol.All(int,vol.Range(min=0,max=11)),
        vol.Optional('value'): bool,
        vol.Optional('expected_slots'): vol.All([bool],vol.Length(min=12,max=12)),
        vol.Optional('day_slots'): vol.All([bool],vol.Length(min=96,max=96)),
        vol.Optional('expected_day_slots'): vol.All([bool],vol.Length(min=96,max=96)),
    })
    hass.services.async_register(DOMAIN, 'schedule', handle_schedule,
                                schema=schema, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, 'history', handle_history,
        schema=vol.Schema({vol.Required('config_entry_id'):str,
                           vol.Optional('action',default='view'):vol.In(['view','newest','older','newer'])}),
        supports_response=SupportsResponse.OPTIONAL)
    return True


class PzpCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        self.client = client
        self.entry = entry
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60))

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self.client.read_all)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from None
        except PzpError as err:
            raise UpdateFailed(str(err)) from None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    client = await hass.async_add_executor_job(
        PzpClient, entry.data["host"], entry.data["username"], entry.data["password"]
    )
    coordinator = PzpCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False

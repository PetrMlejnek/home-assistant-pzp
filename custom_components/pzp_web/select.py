"""Select a local season, with confirmed state and no restored commands."""
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN
from .client import PzpError, SEASONS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PzpSeason(hass.data[DOMAIN][entry.entry_id], entry)])


class PzpSeason(CoordinatorEntity, SelectEntity):
    _attr_name = "PZP Volba sezóny"
    _attr_icon = "mdi:sun-snowflake-variant"
    _attr_options = list(SEASONS)

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_unique_id = entry.entry_id + "_season"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["host"])},
            "name": "PZP – místní nastavení", "manufacturer": "PZP",
            "configuration_url": "http://" + entry.data["host"],
        }

    @property
    def current_option(self):
        return self.coordinator.data.get("season")

    @property
    def extra_state_attributes(self):
        # Public routing metadata only; no address, credentials or session state.
        return {'config_entry_id': self._entry_id}

    @property
    def available(self):
        return super().available and self.coordinator.data.get("season_visible", False)

    async def async_select_option(self, option):
        try:
            state = await self.hass.async_add_executor_job(self.coordinator.client.set_season, option)
        except (PzpError, ValueError) as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(str(err)) from None
        self.coordinator.async_set_updated_data({**self.coordinator.data, **state})

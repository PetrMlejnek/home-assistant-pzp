"""Display the regulator's local automatic/manual mode."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PzpPeriodMode(hass.data[DOMAIN][entry.entry_id], entry)])


class PzpPeriodMode(CoordinatorEntity, SensorEntity):
    _attr_name = "PZP Režim změny období"
    _attr_icon = "mdi:calendar-sync"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id + "_period_mode"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.data["host"])}}

    @property
    def native_value(self):
        return self.coordinator.data.get("period_mode")

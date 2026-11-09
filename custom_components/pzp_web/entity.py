"""Common properties for explicitly mapped local parameters."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN


class PzpParameterEntity(CoordinatorEntity):
    def __init__(self, coordinator, entry, cfg, domain):
        super().__init__(coordinator)
        self.cfg = cfg
        self._attr_name = 'PZP ' + cfg['name']
        self._attr_unique_id = entry.entry_id + '_parameter_' + cfg['code']
        self.entity_id = domain + '.pzp_parametr_' + cfg['code'].lower()
        self._attr_device_info = {'identifiers': {(DOMAIN, entry.data['host'])}}

    @property
    def parameter(self):
        return self.coordinator.data.get('parameters', {}).get(self.cfg['code'], {})

    @property
    def available(self):
        return super().available and self.parameter.get('available', False)

    @property
    def extra_state_attributes(self):
        return {'parametr': self.cfg['code'], 'ulozeni': 'regulátor čerpadla'}

"""Run on disposable Linux HA, with device I/O patched before integration setup."""
import asyncio
import importlib
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from homeassistant.bootstrap import async_from_config_dict
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration


async def smoke(config_dir):
    hass = HomeAssistant(str(config_dir))
    await async_from_config_dict({
        'homeassistant': {'name': 'Synthetic test', 'latitude': 0, 'longitude': 0,
                         'elevation': 0, 'unit_system': 'metric', 'time_zone': 'UTC'},
        'http': {'server_host': '127.0.0.1'},
        'logger': {'default': 'warning'},
    }, hass)
    try:
        integration = await async_get_integration(hass, 'pzp_web')
        await integration.async_get_component()
        module = importlib.import_module('custom_components.pzp_web.client')
        state = {'season': 'Topná sezóna', 'period_mode': 'Ruční', 'season_visible': True}

        def read_all(client):
            return {**state, 'parameters': {code: {'value': '20.0' if cfg['kind'] == 'numeric' else 'Ne', 'available': True}
                    for code, cfg in client.catalog.items()}}

        with patch.object(module.PzpClient, '_request', side_effect=AssertionError('Unexpected physical I/O')), \
             patch.object(module.PzpClient, 'read_state', return_value=state) as read, \
             patch.object(module.PzpClient, 'read_all', read_all):
            flow = await hass.config_entries.flow.async_init('pzp_web', context={'source': 'user'})
            assert flow['type'] == 'form', flow
            result = await hass.config_entries.flow.async_configure(flow['flow_id'], {
                'host': ' PUMP.example:80 ', 'username': 'synthetic', 'password': 'not-a-real-password'})
            assert result['type'] == 'create_entry', result
            await hass.async_block_till_done()
            entry = result['result']
            assert entry.data['host'] == 'pump.example'
            assert entry.unique_id == 'pump.example'
            registry = er.async_get(hass)
            before = {e.unique_id: e.entity_id for e in registry.entities.values() if e.config_entry_id == entry.entry_id}
            assert len(before) == 29, before
            season = hass.states.get(before[entry.entry_id + '_season'])
            assert season.state == 'Topná sezóna', season
            assert season.attributes['config_entry_id'] == entry.entry_id
            calls = read.call_count
            duplicate = await hass.config_entries.flow.async_init('pzp_web', context={'source': 'user'})
            duplicate = await hass.config_entries.flow.async_configure(duplicate['flow_id'], {
                'host': 'pump.example', 'username': 'synthetic', 'password': 'not-a-real-password'})
            assert duplicate['type'] == 'abort', duplicate
            assert read.call_count == calls
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            after = {e.unique_id: e.entity_id for e in registry.entities.values() if e.config_entry_id == entry.entry_id}
            assert before == after
            assert await hass.config_entries.async_unload(entry.entry_id)
            print('PASS: real HA config flow, duplicate detection, all entities, card routing metadata, ID stability, reload and unload; simulated controller only')
    finally:
        await hass.async_stop(force=True)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='pzp-smoke-') as temporary:
        config_dir = Path(temporary)
        shutil.copytree(Path(__file__).resolve().parents[1] / 'custom_components', config_dir / 'custom_components')
        asyncio.run(smoke(config_dir))

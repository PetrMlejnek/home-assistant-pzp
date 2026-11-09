import test from 'node:test';
import assert from 'node:assert/strict';
import { entryReady, resolveEntryId } from '../custom_components/pzp_web/www/pzp-card-utils.js';

test('each card resolves the selected pump independently of its entity name', () => {
  const hass = {states: {
    'select.downstairs': {attributes: {config_entry_id: 'entry-one'}},
    'select.renamed_pump': {attributes: {config_entry_id: 'entry-two'}},
  }};
  assert.equal(resolveEntryId({entity:'select.downstairs'}, hass), 'entry-one');
  assert.equal(resolveEntryId({entity:'select.renamed_pump'}, hass), 'entry-two');
});

test('legacy explicit entry still works during unavailable entity recovery', () => {
  assert.equal(resolveEntryId({config_entry_id:'entry-one',entity:'select.missing'}, {}), 'entry-one');
  assert.equal(entryReady({config_entry_id:'entry-one'}, {}), true);
});

test('waits for delayed entity and never selects an arbitrary pump', () => {
  const config = {entity:'select.pump'};
  assert.equal(entryReady(config, {}), false);
  assert.throws(() => resolveEntryId(config, {}));
  assert.equal(entryReady(config, {states:{'select.pump':{attributes:{config_entry_id:'ready'}}}}), true);
});

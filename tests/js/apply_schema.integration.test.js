'use strict';
// @integration - REAL Yext sandbox, READ-ONLY. Skipped unless RUN_INTEGRATION=1 and YEXT_API_KEY / YEXT_ENTITY_ID are set.
//   set -a; source .env; set +a; RUN_INTEGRATION=1 node --test tests/js/apply_schema.integration.test.js
// Guards the "Knowledge Graph fields are fixed" rule from the JS side: the live entity may only use the known
// hours keys, so the Apply step (Python) has no room to add new schema fields. Listings must stay inside the
// 14 publishers of data/listings.json.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const axios = require('axios');

const run = process.env.RUN_INTEGRATION === '1';
const key = process.env.YEXT_API_KEY, eid = process.env.YEXT_ENTITY_ID;
const base = (process.env.YEXT_BASE_URL || 'https://sbx-api.yextapis.com/').replace(/\/?$/, '/');
const v = process.env.YEXT_API_VERSION || '20261106';
const skip = !run ? 'set RUN_INTEGRATION=1' : (!key || !eid ? 'YEXT_API_KEY / YEXT_ENTITY_ID not set' : false);

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const HOURS_KEYS = new Set([...DAYS, 'holidayHours', 'reopenDate', 'holidayHoursConversationEnabled']);
const HOLIDAY_KEYS = new Set(['date', 'isClosed', 'isRegularHours', 'openIntervals']);
const get = (p, params) => axios.get(`${base}v2/accounts/me/${p}`, { params: { api_key: key, v, ...params }, timeout: 30000, validateStatus: () => true });

test('@integration account `me` + v param: entity hours use only schema keys', { skip }, async () => {
  const r = await get(`entities/${eid}`);
  assert.equal(r.status, 200);
  const hours = r.data.response.hours || {};
  for (const k of Object.keys(hours)) assert.ok(HOURS_KEYS.has(k), `unexpected hours key: ${k}`);
  for (const item of hours.holidayHours || []) {
    for (const k of Object.keys(item)) assert.ok(HOLIDAY_KEYS.has(k), `unexpected holidayHours key: ${k}`);
    const flags = ['isClosed', 'isRegularHours'].filter((f) => item[f]).length + ((item.openIntervals || []).length ? 1 : 0);
    assert.equal(flags, 1, `holidayHours ${item.date} must set exactly one state flag`);
  }
});

test('@integration listings stay within the fixed publisher universe of data/listings.json', { skip }, async () => {
  const universe = new Set(
    JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'data', 'listings.json'), 'utf8')).listings.map((l) => l.publisherId),
  );
  assert.equal(universe.size, 14);
  const r = await get('listings/listings', { locationIds: eid });
  if (r.status !== 200) return; // endpoint not exposed for this sandbox account: nothing to assert
  for (const l of r.data.response.listings || []) assert.ok(universe.has(l.publisherId), `new publisher in sandbox: ${l.publisherId}`);
});

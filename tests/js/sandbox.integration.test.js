'use strict';
// @integration - real Yext sandbox (https://sbx-api.yextapis.com). Skipped unless RUN_INTEGRATION=1 and creds are set.
//   set -a; source .env; set +a; RUN_INTEGRATION=1 node --test tests/js/sandbox.integration.test.js
// Read-only: never writes to the sandbox.
const test = require('node:test');
const assert = require('node:assert/strict');
const axios = require('axios');

const run = process.env.RUN_INTEGRATION === '1';
const key = process.env.YEXT_API_KEY, eid = process.env.YEXT_ENTITY_ID;
const base = (process.env.YEXT_BASE_URL || 'https://sbx-api.yextapis.com/').replace(/\/?$/, '/');
const v = process.env.YEXT_API_VERSION || '20261106';
const skip = !run ? 'set RUN_INTEGRATION=1' : (!key || !eid ? 'YEXT_API_KEY / YEXT_ENTITY_ID not set' : false);
const url = (id) => `${base}v2/accounts/me/entities/${id}`;
const get = (id, params) => axios.get(url(id), { params, timeout: 30000, validateStatus: () => true });

test('@integration GET entity returns 200 and a business name', { skip }, async () => {
  const r = await get(eid, { api_key: key, v });
  assert.equal(r.status, 200);
  assert.ok(r.data.response.name);
});

test('@integration unknown entity id returns 404', { skip }, async () => {
  const r = await get('definitely-not-an-entity-id-123', { api_key: key, v });
  assert.equal(r.status, 404);
});

test('@integration invalid api_key returns 401/403', { skip: !run ? 'set RUN_INTEGRATION=1' : false }, async () => {
  const r = await get(eid || 'any', { api_key: 'invalid-key-for-test', v });
  assert.ok([401, 403].includes(r.status), `got ${r.status}`);
});

test('@integration missing v parameter is rejected with 4xx', { skip }, async () => {
  const r = await get(eid, { api_key: key });
  assert.ok(r.status >= 400 && r.status < 500, `got ${r.status}`);
});

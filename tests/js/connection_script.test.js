'use strict';
// Unit tests for tests/backend_connection_test.js (the Yext connection check run by CI) against a LOCAL STUB.
// Run:  node --test tests/js/
const test = require('node:test');
const assert = require('node:assert/strict');
const { startStub, runConnectionScript, ok, err } = require('./helpers');

const env = (stub, extra = {}) => ({
  YEXT_BASE_URL: stub.base + '/', YEXT_API_KEY: 'test-key', YEXT_ENTITY_ID: 'E1', YEXT_API_VERSION: '20261106', ...extra,
});

test('happy path: GETs /v2/accounts/me/entities/{id} with api_key and v, prints the business name', async (t) => {
  const stub = await startStub([ok('Kahvila Aurora')]);
  t.after(stub.close);
  const r = await runConnectionScript(env(stub));
  assert.match(r.stdout, /Success/);
  assert.match(r.stdout, /Business Name: Kahvila Aurora/);
  assert.equal(stub.requests.length, 1);
  const u = new URL(stub.requests[0].url, 'http://x');
  assert.equal(stub.requests[0].method, 'GET');
  assert.equal(u.pathname, '/v2/accounts/me/entities/E1');          // 'me' instead of the account id
  assert.equal(u.searchParams.get('api_key'), 'test-key');
  assert.equal(u.searchParams.get('v'), '20261106');
});

test('defaults the version parameter to 20261106 when YEXT_API_VERSION is unset', async (t) => {
  const stub = await startStub([ok()]);
  t.after(stub.close);
  const e = env(stub); delete e.YEXT_API_VERSION;
  await runConnectionScript(e);
  assert.equal(new URL(stub.requests[0].url, 'http://x').searchParams.get('v'), '20261106');
});

for (const [status, code, msg] of [[401, 1, 'Invalid API key'], [404, 2000, 'Entity not found'], [429, 5, 'Too many requests']]) {
  test(`HTTP ${status}: reports "Connection failed" with the Yext error body`, async (t) => {
    const stub = await startStub([err(status, code, msg, status === 429 ? { 'Retry-After': '2' } : undefined)]);
    t.after(stub.close);
    const r = await runConnectionScript(env(stub));
    assert.match(r.stderr, /Connection failed/);
    assert.ok(r.stderr.includes(msg), r.stderr);
    assert.doesNotMatch(r.stdout, /Success/);
    assert.equal(stub.requests.length, 1);   // no retry on 429 (documented gap, see below)
  });
}

test('HTTP 500 with a non-JSON body is still reported as a failure', async (t) => {
  const stub = await startStub([{ status: 500, body: 'boom' }]);
  t.after(stub.close);
  const r = await runConnectionScript(env(stub));
  assert.match(r.stderr, /Connection failed/);
});

test('connection refused is reported as a failure', async () => {
  const r = await runConnectionScript({ YEXT_BASE_URL: 'http://127.0.0.1:1/', YEXT_API_KEY: 'k', YEXT_ENTITY_ID: 'E1' });
  assert.match(r.stderr, /Connection failed/);
});

test('missing credentials: no api_key / entity id is sent and the failure is visible', async (t) => {
  const stub = await startStub([err(401, 1, 'Missing api_key')]);
  t.after(stub.close);
  const r = await runConnectionScript({ YEXT_BASE_URL: stub.base + '/' });
  assert.match(r.stderr, /Connection failed/);
  assert.match(r.stdout, /entity: undefined/);                      // prints "undefined" instead of failing fast
});

// ------------------------------------------------------------------ KNOWN GAPS (todo: reported, never fail the run)
test('KNOWN GAP: a failed connection exits non-zero so CI turns red', { todo: 'script only console.errors; exit code is 0, so .github/workflows/backend-test.yml stays green on 401/404/429' }, async (t) => {
  const stub = await startStub([err(401, 1, 'Invalid API key')]);
  t.after(stub.close);
  const r = await runConnectionScript(env(stub));
  assert.notEqual(r.code, 0);
});

test('KNOWN GAP: YEXT_BASE_URL without trailing slash works (Python client and START_HERE use no slash)', { todo: 'URL is built as `${baseUrl}v2/...` so "https://sbx-api.yextapis.com" becomes "https://sbx-api.yextapis.comv2/..."' }, async (t) => {
  const stub = await startStub([ok()]);
  t.after(stub.close);
  const r = await runConnectionScript(env(stub, { YEXT_BASE_URL: stub.base }));   // no trailing slash
  assert.match(r.stdout, /Business Name/);
});

test('KNOWN GAP: a 200 response with an unexpected body is not reported as success', { todo: '"Success!" is printed before response.data.response.name is read, so garbage 200s print both Success and Connection failed' }, async (t) => {
  const stub = await startStub([{ status: 200, body: '<html>maintenance</html>' }]);
  t.after(stub.close);
  const r = await runConnectionScript(env(stub));
  assert.doesNotMatch(r.stdout, /Success/);
});

test('KNOWN GAP: the script has a request timeout', { todo: 'axios call has no timeout; a hung sandbox hangs the CI job until the runner limit' }, async (t) => {
  const stub = await startStub([ok()]);
  t.after(stub.close);
  const src = require('node:fs').readFileSync(require('./helpers').SCRIPT, 'utf8');
  assert.match(src, /timeout\s*:/);
});

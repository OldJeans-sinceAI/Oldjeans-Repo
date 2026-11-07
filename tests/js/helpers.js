'use strict';
// Shared helpers for the JS tests (Node's built-in test runner: `node --test tests/js/`; no extra dependencies).
const http = require('node:http');
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

const SCRIPT = path.join(__dirname, '..', 'backend_connection_test.js');

/** Scripted stub of the Yext API. `script` = [{status, body, headers}]; the last entry repeats. */
function startStub(script) {
  const requests = [];
  let i = 0;
  const server = http.createServer((req, res) => {
    requests.push({ method: req.method, url: req.url, headers: req.headers });
    const step = script[Math.min(i++, script.length - 1)];
    const raw = typeof step.body === 'string' ? step.body : JSON.stringify(step.body);
    res.writeHead(step.status, { 'Content-Type': 'application/json', ...(step.headers || {}) });
    res.end(raw);
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      resolve({
        port: server.address().port,
        base: `http://127.0.0.1:${server.address().port}`,
        requests,
        close: () => new Promise((r) => server.close(r)),
      });
    });
  });
}

/**
 * Run tests/backend_connection_test.js unchanged in a child process.
 * cwd is an empty temp dir so dotenv can NOT pick up the real .env (secrets never reach tests).
 */
function runConnectionScript(env) {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'yext-js-'));
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [SCRIPT], { cwd, env: { PATH: process.env.PATH, ...env } });
    let stdout = '', stderr = '';
    p.stdout.on('data', (d) => (stdout += d));
    p.stderr.on('data', (d) => (stderr += d));
    p.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

const ok = (name = 'Kahvila Aurora') => ({ status: 200, body: { meta: { errors: [] }, response: { name } } });
const err = (status, code, message, headers) => ({
  status, headers, body: { meta: { errors: [{ code, type: 'FATAL_ERROR', message }] }, response: {} },
});

module.exports = { startStub, runConnectionScript, ok, err, SCRIPT };

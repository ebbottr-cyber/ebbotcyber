const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const {
  CI_UI_SMOKE_ARG,
  validateCiUiSmoke,
  isAllowedCiUiRequest,
} = require('../ci-ui-smoke');

const env = {
  GITHUB_ACTIONS: 'true',
  EBBOT_ELECTRON_UI_SMOKE: '1',
  EBBOT_ELECTRON_UI_SMOKE_PORT: '54321',
};
const argv = ['C:\\runner\\win-unpacked\\EBBot.exe', CI_UI_SMOKE_ARG];

test('packaged CI BrowserWindow smoke is tightly restricted to Windows and exact arguments', () => {
  assert.deepEqual(validateCiUiSmoke({ packaged: true, platform: 'win32', env, argv }), {
    requested: true, allowed: true, port: 54321,
  });
  for (const override of [
    { packaged: false },
    { platform: 'linux' },
    { env: { ...env, GITHUB_ACTIONS: 'false' } },
    { env: { ...env, EBBOT_ELECTRON_UI_SMOKE: '0' } },
    { env: { ...env, EBBOT_ELECTRON_UI_SMOKE_PORT: '0' } },
    { env: { ...env, EBBOT_ELECTRON_UI_SMOKE_PORT: '65536' } },
    { env: { ...env, EBBOT_ELECTRON_UI_SMOKE_PORT: '54321z' } },
    { argv: [...argv, '--serve'] },
  ]) {
    assert.equal(validateCiUiSmoke({
      packaged: true, platform: 'win32', env, argv, ...override,
    }).allowed, false);
  }
  assert.deepEqual(validateCiUiSmoke({
    packaged: true, platform: 'win32', env, argv: ['EBBot.exe'],
  }), { requested: false, allowed: false, port: null });
});

test('UI smoke renderer network requests cannot leave loopback', () => {
  assert.equal(isAllowedCiUiRequest('file:///C:/app.asar/renderer/loading.html', 54321), true);
  assert.equal(isAllowedCiUiRequest('http://127.0.0.1:54321/api/health', 54321), true);
  for (const url of [
    'https://github.com/ebbottr-cyber/ebbotcyber/releases',
    'http://localhost:54321/api/health',
    'http://127.0.0.1:54322/api/health',
    'http://192.168.1.10:54321/api/health',
    'http://127.0.0.1:54321.evil.example/',
    'http://127.0.0.1:54321@evil.example/',
    'not-a-url',
  ]) {
    assert.equal(isAllowedCiUiRequest(url, 54321), false, url);
  }
});

test('normal desktop startup and fail-closed updater remain separate from smoke path', () => {
  const mainSource = fs.readFileSync(path.join(__dirname, '..', 'main.js'), 'utf8');
  assert.match(mainSource, /if \(ciUiSmokeRequested\)/);
  assert.match(mainSource, /if \(!ciProbe\.allowed\)/);
  assert.match(mainSource, /app\.whenReady\(\)\.then\(createWindow\)/);
  assert.match(mainSource, /const DESKTOP_UPDATES_ENABLED = false;/);
  assert.match(mainSource, /runCiUiSmoke\(/);

  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json')));
  assert.equal(pkg.build.productName, 'EBBot');
  assert.ok(pkg.build.files.includes('ci-ui-smoke.js'));
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const { isAllowedCiUiRequest, validateCiUiSmoke } = require('../ci-ui-smoke');

test('Turkish React smoke remains opt-in inside packaged Windows CI only', () => {
  const env = {
    GITHUB_ACTIONS: 'true',
    EBBOT_ELECTRON_UI_SMOKE: '1',
    EBBOT_ELECTRON_REACT_SMOKE: '1',
    EBBOT_ELECTRON_UI_SMOKE_PORT: '54321',
  };
  assert.equal(validateCiUiSmoke({
    packaged: true,
    platform: 'win32',
    env,
    argv: ['EBBot.exe', '--ebbot-ci-ui-smoke'],
  }).allowed, true);
  assert.equal(validateCiUiSmoke({
    packaged: false,
    platform: 'win32',
    env,
    argv: ['EBBot.exe', '--ebbot-ci-ui-smoke'],
  }).allowed, false);

  const main = fs.readFileSync(path.join(__dirname, '..', 'main.js'), 'utf8');
  assert.match(main, /reactProbe: process\.env\.EBBOT_ELECTRON_REACT_SMOKE === '1'/);
  assert.match(main, /const DESKTOP_UPDATES_ENABLED = false;/);
  assert.match(main, /EBBOT_ELECTRON_REACT_SMOKE === '1' \? 42 : 0/);
  const probe = fs.readFileSync(
    path.join(__dirname, '..', '..', '..', 'scripts', 'probe_ebbot_packaged_health.py'),
    'utf8',
  );
  assert.match(probe, /expected_exit_code = 42 if react_probe else 0/);
  assert.match(probe, /PASS: packaged Turkish React Usage\/Data, Portfolio, AI Signals, Screening and Settings navigation/);
});

test('CI Electron React smoke checks Turkish real navigation and restricts network', () => {
  for (const pathSuffix of ['/', '/assets/app.js', '/api/v1/auth/status', '/usage', '/data', '/portfolio', '/decision-signals', '/screening', '/settings']) {
    assert.equal(isAllowedCiUiRequest(`http://127.0.0.1:54321${pathSuffix}`, 54321), true);
  }
  assert.equal(isAllowedCiUiRequest('https://api.github.com/', 54321), false);
  assert.equal(isAllowedCiUiRequest('http://localhost:54321/', 54321), false);

  const smoke = fs.readFileSync(path.join(__dirname, '..', 'ci-ui-smoke.js'), 'utf8');
  assert.match(smoke, /if \(reactProbe\)/);
  assert.match(smoke, /localStorage\.setItem\('dsa\.uiLanguage', 'tr'\)/);
  assert.match(smoke, /document\.documentElement\.lang === 'tr'/);
  assert.match(smoke, /Ana menü/);
  assert.match(smoke, /Piyasa Özeti/);
  assert.match(smoke, /Hisse Analizi/);
  const sidebar = fs.readFileSync(
    path.join(__dirname, '..', '..', 'dsa-web', 'src', 'components', 'layout', 'SidebarNav.tsx'),
    'utf8',
  );
  // Equivalent Unicode escape in the TS source must not weaken visible-text assertions.
  assert.ok(
    sidebar.includes('Piyasa Özeti') || sidebar.includes(String.raw`Piyasa \u00d6zeti`),
    'real Turkish Overview nav label missing from SidebarNav source',
  );
  assert.match(sidebar, /Hisse Analizi/);
  assert.match(smoke, /Kullanım/);
  assert.match(smoke, /Veri Merkezi/);
  for (const [route, heading] of [
    ['/portfolio', 'Portföy Yönetimi'],
    ['/decision-signals', 'AI Önerileri'],
    ['/screening', 'Hisse Tarama'],
    ['/settings', 'Ayarlar'],
  ]) {
    assert.ok(smoke.includes("pathname: '" + route + "'"), route);
    assert.ok(smoke.includes("heading: '" + heading + "'"), heading);
  }
  assert.match(smoke, /Never click trade, analysis, screen-run/);

  assert.match(smoke, /\/api\/v1\/analysis\/analyze/);
});

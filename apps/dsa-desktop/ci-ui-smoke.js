'use strict';

// Packaged Electron BrowserWindow smoke, deliberately NOT the production React
// desktop flow. All browser requests are limited to a local frozen health API.
const path = require('node:path');

const CI_UI_SMOKE_ARG = '--ebbot-ci-ui-smoke';

function validateCiUiSmoke({
  packaged = false,
  platform = process.platform,
  env = process.env,
  argv = process.argv,
} = {}) {
  const args = Array.isArray(argv) ? argv.slice(1) : [];
  const requested = args.includes(CI_UI_SMOKE_ARG);
  if (!requested) {
    return { requested: false, allowed: false, port: null };
  }
  const rawPort = String(env.EBBOT_ELECTRON_UI_SMOKE_PORT || '');
  const port = /^[1-9][0-9]{3,4}$/.test(rawPort) ? Number(rawPort) : null;
  const allowed = Boolean(
    packaged
    && platform === 'win32'
    && env.GITHUB_ACTIONS === 'true'
    && env.EBBOT_ELECTRON_UI_SMOKE === '1'
    && args.length === 1
    && args[0] === CI_UI_SMOKE_ARG
    && port !== null
    && port >= 1024
    && port <= 65535
  );
  return { requested: true, allowed, port: allowed ? port : null };
}

function isAllowedCiUiRequest(url, port) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'file:') {
      return true;
    }
    return parsed.protocol === 'http:'
      && parsed.hostname === '127.0.0.1'
      && parsed.port === String(port);
  } catch (_error) {
    return false;
  }
}

async function runCiUiSmoke({ BrowserWindow, session, rootDir, port, reactProbe = false }) {
  if (!session || !session.defaultSession || !session.defaultSession.webRequest) {
    throw new Error('Packaged Electron session is missing');
  }
  // No web/electron-updater/third-party requests from this diagnostic window.
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !isAllowedCiUiRequest(details.url, port) });
  });

  const window = new BrowserWindow({
    width: 1000,
    height: 700,
    show: false,
    webPreferences: {
      preload: path.join(rootDir, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  try {
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    await window.loadFile(path.join(rootDir, 'renderer', 'loading.html'));
    const splash = await window.webContents.executeJavaScript(`({
      title: document.title,
      heading: document.querySelector('h1.title')?.textContent?.trim() || '',
      preloadBridge: typeof window.dsaDesktop?.getUpdateState === 'function'
    })`);
    if (splash.title !== 'EBBot' || splash.heading !== 'EBBot' || !splash.preloadBridge) {
      throw new Error('Packaged EBBot splash or preload bridge failed to render');
    }

    const healthUrl = `http://127.0.0.1:${port}/api/health`;
    await window.loadURL(healthUrl);
    const result = await window.webContents.executeJavaScript(`(async () => {
      const response = await fetch('/api/health', { cache: 'no-store' });
      const payload = await response.json();
      const forbidden = await fetch('/api/v1/analysis/analyze', { cache: 'no-store' });
      return {
        status: response.status,
        payload,
        forbiddenStatus: forbidden.status
      };
    })()`);

    if (result.status !== 200
        || result.payload?.status !== 'ok'
        || result.payload?.probe !== 'offline-packaged'
        || result.forbiddenStatus !== 404) {
      throw new Error('Packaged Electron renderer cannot verify restricted loopback backend');
    }

    console.log('PASS: packaged EBBot BrowserWindow splash, preload and renderer loopback health; analysis unavailable.');

    if (reactProbe) {
      // The frozen backend serves ONLY bundled static assets, canned read-only
      // auth status and /api/health. No normal API endpoints are registered.
      const reactRoot = `http://127.0.0.1:${port}/`;
      await window.loadURL(reactRoot);
      // GitHub's hosted Windows locale is often en-US. Explicitly select
      // Turkish for THIS throwaway Chromium session, then reload the real
      // packaged React app. This does not change product defaults.
      await window.webContents.executeJavaScript(
        "window.localStorage.setItem('dsa.uiLanguage', 'tr')"
      );
      await window.loadURL(reactRoot);
      const navigation = await window.webContents.executeJavaScript(`(async () => {
        const deadline = Date.now() + 45000;
        const waitUntil = async (check) => {
          while (Date.now() < deadline) {
            const result = check();
            if (result) return result;
            await new Promise((resolve) => setTimeout(resolve, 250));
          }
          throw new Error('Timed out while waiting for packaged React route');
        };

        await waitUntil(() => {
          const nav = document.querySelector('nav[aria-label="Ana menü"]');
          return nav && document.documentElement.lang === 'tr'
            && nav.querySelector('a[aria-label="Piyasa Özeti"]')
            && nav.querySelector('a[aria-label="Hisse Analizi"]')
            && nav.querySelector('a[aria-label="Kullanım"]')
            && nav.querySelector('a[aria-label="Veri Merkezi"]');
        });

        const initial = {
          language: document.documentElement.lang,
          nav: document.querySelector('nav[aria-label="Ana menü"]')?.getAttribute('aria-label'),
          rootMounted: !!document.querySelector('#root > *'),
        };
        const usageLink = document.querySelector('nav a[aria-label="Kullanım"]');
        usageLink.click();
        await waitUntil(() => window.location.pathname === '/usage'
          && document.querySelector('main h1')?.textContent?.trim() === 'Token Kullanımı');
        const usage = {
          pathname: window.location.pathname,
          heading: document.querySelector('main h1')?.textContent?.trim() || '',
        };
        const dataLink = document.querySelector('nav a[aria-label="Veri Merkezi"]');
        dataLink.click();
        await waitUntil(() => window.location.pathname === '/data'
          && document.querySelector('main h1')?.textContent?.trim() === 'Veri merkezi');

        // Exercise navigation only. Never click trade, analysis, screen-run,
        // config-save or scheduler controls in this smoke test.
        const checks = [
          { label: 'Portföy', pathname: '/portfolio', heading: 'Portföy Yönetimi' },
          { label: 'AI Önerileri', pathname: '/decision-signals', heading: 'AI Önerileri' },
          { label: 'Hisse Tarama', pathname: '/screening', heading: 'Hisse Tarama' },
          { label: 'Ayarlar', pathname: '/settings', heading: 'Ayarlar' },
        ];
        const checkedPages = [];
        for (const item of checks) {
          const link = document.querySelector('nav a[aria-label="' + item.label + '"]');
          if (!link) throw new Error('Missing Turkish navigation: ' + item.label);
          link.click();
          await waitUntil(() => window.location.pathname === item.pathname
            && document.querySelector('main h1')?.textContent?.trim() === item.heading);
          checkedPages.push({
            pathname: window.location.pathname,
            heading: document.querySelector('main h1')?.textContent?.trim() || '',
          });
        }
        return {
          initial,
          usage,
          data: {
            pathname: '/data',
            heading: 'Veri merkezi',
          },
          checkedPages,
        };
      })()`);

      if (navigation.initial?.language !== 'tr'
        || navigation.initial.nav !== 'Ana menü'
        || !navigation.initial.rootMounted
        || navigation.usage?.pathname !== '/usage'
        || !navigation.usage.heading
        || navigation.data?.pathname !== '/data'
        || !navigation.data.heading
        || !Array.isArray(navigation.checkedPages)
        || navigation.checkedPages.length !== 4
        || navigation.checkedPages.some((page, index) => (
          page.pathname !== ['/portfolio', '/decision-signals', '/screening', '/settings'][index]
          || page.heading !== ['Portföy Yönetimi', 'AI Önerileri', 'Hisse Tarama', 'Ayarlar'][index]
        ))) {
        throw new Error('Packaged Turkish React dashboard or navigation did not render as expected');
      }
      console.log('PASS: packaged Turkish React shell, Usage/Data, Portfolio, AI Signals, Screening and Settings navigation (CI-only, no writes).');
    }
  } finally {
    if (!window.isDestroyed()) {
      window.destroy();
    }
  }
}

module.exports = {
  CI_UI_SMOKE_ARG,
  validateCiUiSmoke,
  isAllowedCiUiRequest,
  runCiUiSmoke,
};

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

async function runCiUiSmoke({ BrowserWindow, session, rootDir, port }) {
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

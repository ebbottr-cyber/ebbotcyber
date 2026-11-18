import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (name) => readFileSync(resolve(project, name), 'utf8');
const manifest = JSON.parse(read('public/manifest.webmanifest'));

test('manifest is Turkish and has safe root scope and standalone mode', () => {
  assert.equal(manifest.id, '/');
  assert.equal(manifest.scope, '/');
  assert.equal(manifest.start_url, '/');
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.lang, 'tr');
  assert.equal(manifest.short_name, 'EBBot');
  for (const [size, purpose] of [['192x192', 'any'], ['512x512', 'any'], ['512x512', 'maskable']]) {
    assert.ok(manifest.icons.some((icon) => icon.sizes === size && icon.purpose === purpose));
  }
});

test('actual PWA icon PNG headers match manifest sizes', () => {
  for (const icon of manifest.icons) {
    const file = resolve(project, 'public', icon.src.slice(1));
    assert.ok(existsSync(file), file);
    const buf = readFileSync(file);
    assert.equal(buf.subarray(1, 4).toString('utf8'), 'PNG');
    assert.equal(buf.readUInt32BE(16) + 'x' + buf.readUInt32BE(20), icon.sizes);
  }
  const apple = readFileSync(resolve(project, 'public/icons/ebbot-apple-180.png'));
  assert.equal(apple.readUInt32BE(16), 180);
  assert.equal(apple.readUInt32BE(20), 180);
});

test('index includes PWA and Apple metadata and no Vite placeholder', () => {
  const html = read('index.html');
  for (const term of ['lang="tr"', '/manifest.webmanifest', '/icons/ebbot-apple-180.png', '/icons/ebbot.svg']) {
    assert.ok(html.includes(term), term);
  }
  assert.ok(html.includes("storedTheme : 'light'"));
  assert.ok(!html.includes('vite.svg'));
});

test('registration is production and secure context only', () => {
  assert.ok(read('src/main.tsx').includes('if (import.meta.env.PROD) registerPwa()'));
  assert.ok(read('src/pwa/registerPwa.ts').includes('window.isSecureContext'));
  assert.ok(read('src/pwa/registerPwa.ts').includes("updateViaCache: 'none'"));
  assert.ok(read('src/components/theme/ThemeProvider.tsx').includes('defaultTheme="light"'));
});

function worker(networkFails = false) {
  const handlers = new Map(), writes = [];
  const context = {
    URL, Promise, Response,
    self: {
      location: { origin: 'https://ebbot.example' },
      addEventListener: (type, cb) => handlers.set(type, cb),
      skipWaiting: async () => {},
      clients: { claim: async () => {} },
    },
    caches: {
      open: async () => ({ addAll: async (values) => writes.push(...values) }),
      match: async (u) => u === '/offline.html' ? { offline: true } : undefined,
      keys: async () => [],
      delete: async () => true,
    },
    fetch: async (_request, opts) => {
      assert.equal(opts.cache, 'no-store');
      if (networkFails) throw Error('offline');
      return { online: true };
    },
  };
  vm.runInNewContext(read('public/sw.js'), context, { filename: 'sw.js' });
  return { handlers, writes };
}
const event = (mode, url, method = 'GET') => {
  let response;
  return {
    request: { mode, url, method },
    respondWith: (value) => { response = value; },
    get response() { return response; },
  };
};

test('service worker caches public offline shell only', async () => {
  const sw = worker();
  let pending;
  sw.handlers.get('install')({ waitUntil: (p) => { pending = p; } });
  await pending;
  assert.deepEqual(sw.writes, ['/offline.html', '/icons/ebbot-192.png']);
  assert.ok(!read('public/sw.js').includes('cache.put('));
});

test('API, POST, assets and cross-origin requests bypass worker', () => {
  const sw = worker();
  for (const item of [
    event('cors', 'https://ebbot.example/api/v1/history'),
    event('navigate', 'https://ebbot.example/api/v1/history'),
    event('navigate', 'https://ebbot.example/docs'),
    event('navigate', 'https://ebbot.example/redoc'),
    event('navigate', 'https://ebbot.example/portfolio', 'POST'),
    event('navigate', 'https://elsewhere.example/'),
    event('no-cors', 'https://ebbot.example/assets/main.js'),
  ]) {
    sw.handlers.get('fetch')(item);
    assert.equal(item.response, undefined);
  }
});

test('normal navigations are online only and never cache private responses', async () => {
  const sw = worker();
  const nav = event('navigate', 'https://ebbot.example/portfolio');
  sw.handlers.get('fetch')(nav);
  assert.deepEqual(await nav.response, { online: true });
});

test('offline navigations show only the public offline notice', async () => {
  const sw = worker(true);
  const nav = event('navigate', 'https://ebbot.example/decision-signals');
  sw.handlers.get('fetch')(nav);
  assert.deepEqual(await nav.response, { offline: true });
});

test('built frontend includes PWA assets if CI requests build verification', () => {
  if (process.env.PWA_REQUIRE_BUILD !== '1') return;
  const dist = resolve(project, '../../static');
  for (const file of ['index.html', 'sw.js', 'manifest.webmanifest', 'offline.html',
    'icons/ebbot.svg', 'icons/ebbot-apple-180.png',
    ...manifest.icons.map((icon) => icon.src.slice(1))]) {
    assert.ok(existsSync(resolve(dist, file)), file);
  }
});

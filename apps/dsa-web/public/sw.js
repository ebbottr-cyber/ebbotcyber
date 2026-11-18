/* EBBot service worker — never cache private, API or trading data. */
const EBBOT_SHELL_CACHE = 'ebbot-offline-static-v1';
const EBBOT_OFFLINE_PAGE = '/offline.html';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(EBBOT_SHELL_CACHE)
      .then((cache) => cache.addAll([EBBOT_OFFLINE_PAGE, '/icons/ebbot-192.png']))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key.startsWith('ebbot-offline-static-') && key !== EBBOT_SHELL_CACHE)
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')
      || url.pathname === '/docs' || url.pathname.startsWith('/docs/')
      || url.pathname === '/redoc' || url.pathname === '/openapi.json') return;

  // Navigation stays network-only, including login and reports.
  event.respondWith(
    fetch(request, { cache: 'no-store' })
      .catch(async () => (await caches.match(EBBOT_OFFLINE_PAGE)) || Response.error()),
  );
});

/** Register the public-only offline notice in production over HTTPS/localhost. */
export function registerPwa(): void {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;

  const register = async () => {
    try {
      await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      });
    } catch (error) {
      // The online application remains usable if PWA registration fails.
      console.warn('[EBBot PWA] Çevrimdışı ekranı etkinleştirilemedi.', error);
    }
  };

  if (document.readyState === 'complete') {
    void register();
  } else {
    window.addEventListener('load', () => void register(), { once: true });
  }
}

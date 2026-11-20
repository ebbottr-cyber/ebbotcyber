import { expect, test } from '@playwright/test';

// A browser smoke check for the real, merged React route. All API responses are
// local fixtures; no wallet, provider calls, scanning, strategy training or orders.
test.use({ locale: 'tr-TR' });

test('dated Solana archive quality appears on desktop and mobile without scanning', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem('dsa.uiLanguage', 'tr'));
  const attemptedWrites: string[] = [];

  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (!pathname.startsWith('/api/')) return route.continue();
    if (route.request().method() !== 'GET') attemptedWrites.push(pathname);
    if (pathname === '/api/v1/auth/status') {
      return route.fulfill({ json: {
        authEnabled: false, loggedIn: true, setupState: 'no_password',
        passwordSet: false, passwordChangeable: false,
      } });
    }
    if (pathname === '/api/v1/meme-coins/status') {
      return route.fulfill({ json: {
        available: true, live_enabled: false, trading_enabled: false,
        strategies: ['new_coin_hunter', 'momentum_watcher'],
      } });
    }
    return route.fulfill({ json: { items: [], total: 0, enabled: false, available: false } });
  });

  for (const [device, width, height] of [
    ['desktop', 1440, 900], ['mobile', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.goto('/meme-coins');
    const panel = page.getByTestId('solana-archive-quality');
    await expect(panel).toBeVisible({ timeout: 15000 });
    await expect(panel.getByRole('heading', { name: 'Solana arşiv veri kalitesi' })).toBeVisible();
    await expect(panel.getByTestId('archive-quality-valid')).toHaveText('9');
    await expect(panel.getByTestId('archive-quality-missing')).toHaveText('3');
    await expect(panel.getByTestId('archive-quality-blocked')).toHaveText('18');
    await expect(panel.getByTestId('archive-quality-watch')).toHaveText('0');
    await expect(panel.getByText(/Anlık veri değildir ve otomatik güncellenmez/)).toBeVisible();
    await expect(panel.getByRole('link', { name: 'GitHub Actions #44791912581' })).toHaveAttribute('href',
      'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44791912581');
    await expect(page.getByRole('button', { name: 'Coinleri tara' })).toBeDisabled();
    await expect(panel.getByRole('button')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    const screenshot = testInfo.outputPath(`solana-quality-${device}.png`);
    await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled' });
    await testInfo.attach(`solana-quality-${device}`, { path: screenshot, contentType: 'image/png' });
  }

  expect(attemptedWrites).toEqual([]);
});

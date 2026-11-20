import { expect, test } from '@playwright/test';

test.use({ locale: 'tr-TR' });

async function mockOnlyExistingApi(page: import('@playwright/test').Page, writes: string[]) {
  await page.addInitScript(() => localStorage.setItem('dsa.uiLanguage', 'tr'));
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (route.request().method() !== 'GET') writes.push(path);
    if (path === '/api/v1/auth/status') {
      return route.fulfill({ json: {
        authEnabled: false, loggedIn: true, setupState: 'no_password',
        passwordSet: false, passwordChangeable: false,
      } });
    }
    if (path === '/api/v1/meme-coins/status') {
      return route.fulfill({ json: {
        available: true, live_enabled: false, trading_enabled: false,
        strategies: ['new_coin_hunter', 'momentum_watcher'],
      } });
    }
    return route.fulfill({ json: { items: [], total: 0, enabled: false, available: false } });
  });
}

test('reviewed Solana quality summary loads on desktop and mobile without API writes', async ({ page }, testInfo) => {
  const writes: string[] = [];
  await mockOnlyExistingApi(page, writes);
  for (const [label, width, height] of [
    ['desktop', 1440, 900],
    ['mobile', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await page.goto('/meme-coins');
    const panel = page.getByTestId('solana-archive-quality');
    await expect(panel.getByRole('heading', { name: 'Solana arşiv veri kalitesi' })).toBeVisible();
    await expect(panel.getByTestId('archive-quality-valid')).toHaveText('9');
    await expect(panel.getByTestId('archive-quality-missing')).toHaveText('3');
    await expect(panel.getByTestId('archive-quality-blocked')).toHaveText('18');
    await expect(panel.getByTestId('archive-quality-watch')).toHaveText('0');
    await expect(panel.getByText(/20 Kasım 2026/)).toBeVisible();
    await expect(panel.getByRole('link', { name: 'GitHub Actions #44791912581' })).toHaveAttribute('href',
      'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44791912581');
    await expect(page.getByRole('button', { name: 'Coinleri tara' })).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

    const file = testInfo.outputPath(`reviewed-quality-${label}.png`);
    await page.screenshot({ path: file, animations: 'disabled', fullPage: true });
    await testInfo.attach(`reviewed-quality-${label}`, { path: file, contentType: 'image/png' });
  }
  expect(writes).toEqual([]);
});

test('unreviewed or unavailable JSON never becomes a numeric quality or trading summary', async ({ page }) => {
  const writes: string[] = [];
  await mockOnlyExistingApi(page, writes);
  await page.route('**/solana-quality-reviewed.json', async (route) => route.fulfill({
    json: { schema_version: 1, trading_enabled: true },
  }));
  await page.goto('/meme-coins');
  const panel = page.getByTestId('solana-archive-quality');
  await expect(panel.getByRole('alert')).toBeVisible();
  await expect(panel.getByTestId('archive-quality-valid')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Coinleri tara' })).toBeDisabled();
  expect(writes).toEqual([]);
});

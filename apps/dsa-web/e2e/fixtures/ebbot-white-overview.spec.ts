import { expect, test, type Page } from '@playwright/test';

// Pure fixture: no live credentials, financial APIs, real devices or trade execution.
const market = {
  as_of: '2026-11-18T10:00:00+00:00',
  cadence: 'delayed_daily',
  items: [
    { key: 'bist100', label: 'BIST 100', symbol: 'XU100.IS', currency: 'TRY',
      price: 11010.5, change_pct: 1.25, as_of: '2026-11-17', status: 'ready',
      source: 'Yahoo Finance (fixture)', note: 'Günlük fiyat verisi' },
    { key: 'bist30', label: 'BIST 30', symbol: 'XU030.IS', currency: 'TRY',
      price: null, change_pct: null, as_of: '2026-10-01', status: 'stale',
      source: 'Yahoo Finance (fixture)', note: 'Eski veri' },
    { key: 'usdtry', label: 'USD/TRY', symbol: 'TRY=X', currency: 'TRY',
      price: 43.1254, change_pct: -0.14, as_of: '2026-11-17', status: 'ready',
      source: 'Yahoo Finance (fixture)', note: 'Günlük fiyat verisi' },
    { key: 'eurtry', label: 'EUR/TRY', symbol: 'EURTRY=X', currency: 'TRY',
      price: 50.09, change_pct: 0.13, as_of: '2026-11-17', status: 'ready',
      source: 'Yahoo Finance (fixture)', note: 'Günlük fiyat verisi' },
    { key: 'gramgold', label: 'Gram Altın', symbol: null, currency: 'TRY/g',
      price: null, change_pct: null, as_of: null, status: 'unavailable',
      source: null, note: 'Doğrulanmış TRY/gram kaynağı henüz bağlı değil' },
  ],
};
const stockHistory = {
  stock_code: 'THYAO.IS', stock_name: 'Türk Hava Yolları', period: 'daily',
  data: [
    { date: '2026-11-16', open: 312, high: 320, low: 308, close: 318, volume: 20000 },
    { date: '2026-11-17', open: 318, high: 324, low: 315, close: 322, volume: 24000 },
  ],
};
const reports = [
  { id: 7, query_id: 'q7', stock_code: 'THYAO.IS', stock_name: 'Türk Hava Yolları',
    report_type: 'detailed', created_at: '2026-11-17T09:00:00Z',
    current_price: 322, change_pct: 2.18, analysis_summary: 'Kayıtlı analiz özeti' },
  { id: 6, query_id: 'q6', stock_code: 'THYAO.IS', stock_name: 'Türk Hava Yolları',
    report_type: 'detailed', created_at: '2026-11-16T09:00:00Z',
    current_price: 318, change_pct: 1.1 },
];

async function stubOverview(page: Page, options: { marketError?: boolean; empty?: boolean } = {}) {
  const writes: string[] = [];
  let marketLoads = 0;
  await page.addInitScript(() => window.localStorage.setItem('dsa.uiLanguage', 'tr'));
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (request.method() !== 'GET') writes.push(path);
    let json: unknown = { items: [], total: 0, page: 1, limit: 20 };
    if (path.endsWith('/auth/status')) {
      json = { authEnabled: false, loggedIn: true, passwordSet: false,
        passwordChangeable: false, setupState: 'no_password' };
    } else if (path === '/api/v1/data/tr-market-overview') {
      marketLoads += 1;
      if (options.marketError) return route.fulfill({ status: 503, json: { detail: 'Fixture no quote' } });
      json = options.empty ? { ...market, items: [] } : market;
    } else if (path === '/api/v1/history') {
      json = { items: options.empty ? [] : reports, total: options.empty ? 0 : 2, page: 1, limit: 60 };
    } else if (path.endsWith('/stocks/THYAO.IS/history')) {
      json = stockHistory;
    } else if (path.endsWith('/stocks/watchlist')) {
      json = { stock_codes: options.empty ? [] : ['THYAO.IS', 'ASELS.IS'] };
    } else if (path === '/api/v1/analysis/tasks') {
      json = { tasks: [], total: 0 };
    } else if (path === '/api/v1/portfolio/snapshot') {
      json = { currency: 'TRY', as_of: '2026-11-17',
        account_count: 1, total_equity: 12000, total_cash: 2000,
        total_market_value: 10000, fx_stale: false };
    } else if (path === '/api/v1/portfolio/risk') {
      json = { concentration: { top_weight_pct: 42, alert: false },
        drawdown: { current_drawdown_pct: 3, alert: false },
        stop_loss: { triggered_count: 0 } };
    } else if (path === '/api/v1/alerts/triggers') {
      json = { items: [], total: 0 };
    }
    return route.fulfill({ json });
  });
  return { writes, get marketLoads() { return marketLoads; } };
}

test('white EBBot screen fits small phones, tablets and desktop with functioning mobile navigation', async ({ page }, testInfo) => {
  const mock = await stubOverview(page);
  await page.goto('/overview');
  const screen = page.getByTestId('ebbot-white-overview');
  await expect(screen).toBeVisible();
  await expect(screen.getByRole('heading', { name: 'Piyasa Özeti' })).toBeVisible();
  await expect(page.getByTestId('turkey-market-cards').getByRole('article', { name: 'BIST 100' })).toContainText('11.010,50');
  await expect(page.getByTestId('candle-scroll')).toBeVisible();
  await expect(page.getByTestId('technical-indicator-panel')).toBeVisible();
  await expect(page.getByText('En az 15 kapanış gerekli.')).toBeVisible();

  for (const [name, width, height] of [
    ['small-iphone', 320, 720],
    ['iphone', 390, 844],
    ['android-large', 430, 932],
    ['tablet', 768, 1024],
    ['desktop', 1440, 900],
  ] as const) {
    await page.setViewportSize({ width, height });
    await expect.poll(() => page.evaluate(() => ({
      doc: document.documentElement.scrollWidth,
      view: document.documentElement.clientWidth,
    }))).toEqual({ doc: width, view: width });
    await expect(page.getByTestId('ebbot-white-overview')).toBeVisible();
    if (width < 640) {
      await expect(page.getByRole('navigation', { name: 'Mobil hızlı gezinme' })).toBeVisible();
      const metrics = await page.getByRole('navigation', { name: 'Mobil hızlı gezinme' }).evaluate((el) => {
        const rect = el.getBoundingClientRect();
        return { left: rect.left, right: rect.right, bottom: rect.bottom };
      });
      expect(metrics.left).toBeGreaterThanOrEqual(-0.1);
      expect(metrics.right).toBeLessThanOrEqual(width + 0.1);
      expect(metrics.bottom).toBeCloseTo(height, 0);
    } else {
      await expect(page.getByRole('navigation', { name: 'Mobil hızlı gezinme' })).toBeHidden();
    }
    const shot = testInfo.outputPath('ebbot-overview-' + name + '.png');
    await page.screenshot({ path: shot, animations: 'disabled', fullPage: false });
    await testInfo.attach(name, { path: shot, contentType: 'image/png' });
  }
  expect(mock.writes).toEqual([]);
});

test('market data and chart are read-only, errors and missing gold price never turn into fake numbers', async ({ page }) => {
  const mock = await stubOverview(page, { marketError: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await expect(page.getByText(/Bağlanamayan bölümler:.*Türkiye piyasaları/)).toBeVisible();
  for (const label of ['BIST 100', 'BIST 30', 'USD/TRY', 'EUR/TRY', 'Gram Altın']) {
    await expect(page.getByRole('article', { name: label })).toContainText('Kaynağa erişilemedi');
  }
  const count = mock.marketLoads;
  await page.getByRole('button', { name: 'Yenile' }).click();
  await expect.poll(() => mock.marketLoads).toBeGreaterThan(count);
  await expect(page.getByRole('article', { name: 'Gram Altın' })).toContainText('—');
  expect(mock.writes).toEqual([]);
});

test('empty portfolio and no analysis data keep transparent placeholders at narrow widths', async ({ page }) => {
  const mock = await stubOverview(page, { empty: true });
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/overview');
  await expect(page.getByText('Henüz analiz raporu yok')).toBeVisible();
  await expect(page.getByRole('article', { name: 'Gram Altın' })).toContainText('—');
  await expect(page.getByTestId('turkey-market-cards')).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(mock.writes).toEqual([]);
});

test('mobile bottom menu navigates to existing portfolio panel', async ({ page }) => {
  await stubOverview(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  const nav = page.getByRole('navigation', { name: 'Mobil hızlı gezinme' });
  await expect(nav).toBeVisible();
  await nav.getByRole('button', { name: 'Portföy' }).click();
  await expect(page).toHaveURL(/\/portfolio$/);
});

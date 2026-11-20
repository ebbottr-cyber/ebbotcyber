import { expect, test } from '@playwright/test';

// No page.route mocks: requests traverse Chromium -> Vite proxy -> actual FastAPI.
// The configured backend is loopback-only and has its startup lifespan disabled.
// This spec must never issue a login POST, invoke a scan, or send trade requests.

test('real FastAPI health and authentication are accessible through the browser proxy', async ({ page, request }) => {
  await page.goto('/login');

  const health = await request.get('/api/v1/health');
  expect(health.status()).toBe(200);
  expect((await health.json()).status).toBe('ok');

  const status = await request.get('/api/v1/auth/status');
  expect(status.status()).toBe(200);
  const auth = await status.json();
  expect(auth.authEnabled).toBe(true);
  expect(auth.loggedIn).toBe(false);
  expect(auth.passwordSet).toBe(false);

  // Confirm Chromium itself can use the same real proxy, not just APIRequestContext.
  const browserAuth = await page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/status');
    return { code: response.status, data: await response.json() };
  });
  expect(browserAuth.code).toBe(200);
  expect(browserAuth.data.authEnabled).toBe(true);

  // First-time setup is displayed but NOT submitted. No account is changed.
  await expect(page.locator('#password')).toBeVisible();
  await expect(page.locator('#passwordConfirm')).toBeVisible();
});

test('unauthenticated portfolio HTTP access fails closed and private UI redirects to login', async ({ page, request }) => {
  const protectedResponse = await request.get('/api/v1/portfolio/snapshot');
  expect(protectedResponse.status()).toBe(401);
  expect((await protectedResponse.json()).error).toBe('unauthorized');

  await page.goto('/portfolio');
  await expect(page).toHaveURL(/\\/login(?:\\?|$)/);
  await expect(page.locator('#password')).toBeVisible();
});

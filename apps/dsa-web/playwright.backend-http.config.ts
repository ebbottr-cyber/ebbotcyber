import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Isolated real HTTP smoke: the Python FastAPI app and Vite are both bound to loopback.
// No mocked API responses, login mutations, exchange credentials, trade execution,
// or scheduler startup. The backend runs with its lifespan disabled.
const cwd = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(cwd, '../..');

export default defineConfig({
  testDir: './e2e/backend-integration',
  outputDir: './test-results/backend-integration',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    locale: 'tr-TR',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'python -m uvicorn api.app:create_app --factory --lifespan off --host 127.0.0.1 --port 8000',
      cwd: root,
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173 --strictPort',
      cwd,
      url: 'http://127.0.0.1:4173/login',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

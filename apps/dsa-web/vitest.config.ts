import { configDefaults, defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    // The PWA smoke is written for Node's built-in test runner, not Vitest.
    // Exclude only that runner-specific file, never business/UI tests.
    exclude: [...configDefaults.exclude, 'e2e/**', 'playwright.config.ts', 'tests/pwa-smoke.test.mjs'],
  },
});

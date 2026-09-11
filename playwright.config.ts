import { defineConfig, devices } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { BASE_URL, DJANGO_PORT, VITE_PORT } from './e2e/constants.ts';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SERVER_DIR = path.join(ROOT, 'server');
const TEST_RESULTS_DIR = path.join(ROOT, 'test-results');
const DATABASE_PATH = path.join(TEST_RESULTS_DIR, 'e2e.sqlite3');
const PYTHON = path.join(ROOT, '.venv', 'bin', 'python');

// Playwright borra `outputDir` (por defecto test-results/) antes de arrancar
// webServer. Como Django necesita test-results/ ya creada para abrir el
// sqlite en cuanto arranca, el reporter/trace/etc. usan una subcarpeta propia
// que sí puede borrarse en cada corrida sin arrastrar la base de datos.
mkdirSync(TEST_RESULTS_DIR, { recursive: true });

// Suite aislada de los servidores de desarrollo reales (5173/8000, db.sqlite3):
// puertos y base de datos propios, arrancados únicamente por webServer.
export default defineConfig({
  testDir: './e2e',
  // *.e2e.ts (no *.spec.ts): vitest usa el include por defecto **/*.{test,spec}.ts
  // y sin esto recogería también estos archivos de Playwright.
  testMatch: '**/*.e2e.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'line',
  outputDir: path.join(TEST_RESULTS_DIR, 'artifacts'),
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: `"${PYTHON}" manage.py runserver 127.0.0.1:${DJANGO_PORT} --noreload`,
      cwd: SERVER_DIR,
      port: DJANGO_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        ...process.env,
        DATABASE_PATH,
        DJANGO_CSRF_ORIGINS: BASE_URL,
      },
    },
    {
      command: `npx vite --config e2e/vite.e2e.config.ts --host 127.0.0.1 --port ${VITE_PORT} --strictPort`,
      cwd: ROOT,
      port: VITE_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});

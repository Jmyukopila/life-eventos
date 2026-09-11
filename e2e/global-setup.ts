import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { SITE_SETTINGS, STAFF_PASSWORD, STAFF_USERNAME } from './constants.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const SERVER_DIR = path.join(ROOT, 'server');
const TEST_RESULTS_DIR = path.join(ROOT, 'test-results');
const DATABASE_PATH = path.join(TEST_RESULTS_DIR, 'e2e.sqlite3');
const PYTHON = path.join(ROOT, '.venv', 'bin', 'python');

export default function globalSetup() {
  mkdirSync(TEST_RESULTS_DIR, { recursive: true });
  for (const suffix of ['', '-journal', '-wal', '-shm']) {
    const file = `${DATABASE_PATH}${suffix}`;
    if (existsSync(file)) rmSync(file);
  }

  const djangoEnv = { ...process.env, DATABASE_PATH };
  const run = (args: string[]) => execFileSync(PYTHON, args, { cwd: SERVER_DIR, env: djangoEnv, stdio: 'inherit' });

  run(['manage.py', 'migrate', '--noinput']);
  run(['manage.py', 'seed_demo']);

  execFileSync(PYTHON, [path.join(HERE, 'prepare-db.py')], {
    cwd: ROOT,
    env: {
      ...djangoEnv,
      E2E_STAFF_USERNAME: STAFF_USERNAME,
      E2E_STAFF_PASSWORD: STAFF_PASSWORD,
      E2E_ORG: SITE_SETTINGS.organization,
      E2E_CONTACT_EMAIL: SITE_SETTINGS.contact_email,
      E2E_CONTACT_PHONE: SITE_SETTINGS.contact_phone,
      E2E_ADDRESS: SITE_SETTINGS.address,
      E2E_PRIVACY_POLICY: SITE_SETTINGS.privacy_policy,
      E2E_PRIVACY_VERSION: SITE_SETTINGS.privacy_version,
      E2E_RETENTION_DAYS: String(SITE_SETTINGS.retention_days),
    },
    stdio: 'inherit',
  });
}

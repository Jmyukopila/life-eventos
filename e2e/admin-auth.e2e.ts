import { test, expect } from '@playwright/test';
import { STAFF_USERNAME } from './constants.ts';
import { loginAsAdmin } from './fixtures.ts';

test.describe('Acceso al panel de administración', () => {
  test('sin sesión, #/admin pide credenciales', async ({ page }) => {
    await page.goto('/#/admin');
    await expect(page.getByRole('heading', { name: 'Bienvenido de nuevo' })).toBeVisible();
    await expect(page.getByLabel('Usuario')).toBeVisible();
    await expect(page.getByLabel('Contraseña')).toBeVisible();
  });

  test('credenciales inválidas se rechazan', async ({ page }) => {
    await page.goto('/#/admin');
    // Usuario distinto del que sí funciona: evita que django-axes bloquee la
    // cuenta real de personal usada en el resto de la suite.
    await page.getByLabel('Usuario').fill('usuario-que-no-existe-e2e');
    await page.getByLabel('Contraseña').fill('cualquier-password-larga-000');
    await page.getByRole('button', { name: 'Ingresar al panel' }).click();
    await expect(page.getByRole('alert')).toContainText('Credenciales inválidas');
  });

  test('credenciales correctas entran al panel', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByText(STAFF_USERNAME)).toBeVisible();
  });
});

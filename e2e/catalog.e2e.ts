import { test, expect } from '@playwright/test';
import { EVENT_TITLES } from './constants.ts';

test.describe('Catálogo público', () => {
  test('carga y muestra los 6 eventos sembrados', async ({ page }) => {
    await page.goto('/#/');
    for (const title of Object.values(EVENT_TITLES)) {
      await expect(page.getByRole('link', { name: title, exact: true })).toBeVisible();
    }
  });

  test('el filtro por categoría acota la lista', async ({ page }) => {
    await page.goto('/#/');
    await page.getByRole('button', { name: 'Grupos de conexión', exact: true }).click();
    await expect(page.getByRole('link', { name: EVENT_TITLES.grupos, exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: EVENT_TITLES.servicio, exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: EVENT_TITLES.jovenes, exact: true })).toHaveCount(0);
  });

  test('la búsqueda por texto encuentra un evento por su título', async ({ page }) => {
    await page.goto('/#/');
    await page.getByLabel('Buscar eventos').fill('vida se comparte');
    await expect(page.getByRole('link', { name: EVENT_TITLES.grupos, exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: EVENT_TITLES.familias, exact: true })).toHaveCount(0);
  });
});

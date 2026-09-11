import { test, expect } from '@playwright/test';
import { uniqueSuffix } from './constants.ts';
import { loginAsAdmin } from './fixtures.ts';

test('crear un evento en el panel lo publica en el catálogo público', async ({ page }) => {
  const title = `Evento E2E ${uniqueSuffix()}`;

  await loginAsAdmin(page);
  await page.getByRole('button', { name: 'Crear evento' }).click();
  await expect(page.getByRole('heading', { name: 'Crear un evento' })).toBeVisible();

  await page.getByLabel('Nombre del evento').fill(title);
  await page.getByLabel('Categoría').selectOption('Jóvenes');
  await page.getByLabel('Estado').selectOption('published');
  await page.getByLabel('Resumen').fill('Resumen del evento creado por la suite E2E.');
  await page.getByLabel('Descripción completa').fill('Descripción larga del evento creado por la suite E2E de Playwright.');
  await page.getByLabel('Inicio *').fill('2026-12-15T10:00');
  await page.getByLabel('Lugar o dirección').fill('Casa Life · Sede E2E');
  await page.getByLabel('Cupos totales').fill('40');

  await page.getByRole('button', { name: 'Guardar evento' }).click();
  await expect(page.getByText('Evento guardado correctamente.')).toBeVisible();

  await page.goto('/#/');
  await expect(page.getByRole('link', { name: title, exact: true })).toBeVisible();
});

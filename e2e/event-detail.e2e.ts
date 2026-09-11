import { test, expect } from '@playwright/test';
import { EVENT_TITLES } from './constants.ts';
import { openEvent } from './fixtures.ts';

test('el detalle del evento muestra la descripción y el botón de inscripción', async ({ page }) => {
  await openEvent(page, EVENT_TITLES.servicio);
  await expect(page.getByText('Vamos a dedicar la mañana a preparar y entregar ayudas', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Quiero participar' })).toBeVisible();
});

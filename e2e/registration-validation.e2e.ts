import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import { fillIdentityStep, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

test('sin marcar los consentimientos obligatorios no se puede confirmar la inscripción', async ({ page }) => {
  const suffix = uniqueSuffix();
  await openEvent(page, EVENT_TITLES.encuentro);
  await openRegistrationForm(page);
  await fillIdentityStep(page, { name: `Sin Consentir ${suffix}`, email: `sin-consentir-${suffix}@example.com` });
  await submitStep(page);

  await page.getByRole('radio', { name: 'Sí' }).check();
  await submitStep(page);
  // "notes" es opcional: se puede continuar sin responderla.
  await submitStep(page);

  await expect(page.getByRole('heading', { name: 'Antes de reservar tu lugar' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirmar inscripción' }).click();

  // Los checkboxes son obligatorios (required nativo): el navegador bloquea el
  // envío, el modal sigue en el paso de consentimientos y no hay referencia.
  await expect(page.getByRole('heading', { level: 2, name: 'Inscríbete al evento' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Antes de reservar tu lugar' })).toBeVisible();
  await expect(page.getByText(/^LIFE-[0-9A-F]{12}$/)).toHaveCount(0);
});

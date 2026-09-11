import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import { checkBaseConsents, expectReference, fillIdentityStep, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

test('la misma persona no puede inscribirse dos veces al mismo evento', async ({ page }) => {
  const suffix = uniqueSuffix();
  const identity = { name: `Duplicado Test ${suffix}`, email: `duplicado-${suffix}@example.com` };

  await openEvent(page, EVENT_TITLES.familias);
  await openRegistrationForm(page);
  await fillIdentityStep(page, identity);
  await submitStep(page);
  await page.getByLabel('¿En qué actividad te gustaría participar?').selectOption('Juegos en familia');
  await submitStep(page);
  await checkBaseConsents(page);
  await submitStep(page);
  await expectReference(page);
  await page.getByRole('button', { name: 'Volver al evento' }).click();

  // Segundo intento: mismo nombre y correo, mismo evento, otro request_id (el
  // formulario genera uno nuevo cada vez que se monta) -> 409 already_registered.
  await openRegistrationForm(page);
  await fillIdentityStep(page, identity);
  await submitStep(page);
  await page.getByLabel('¿En qué actividad te gustaría participar?').selectOption('Juegos en familia');
  await submitStep(page);
  await checkBaseConsents(page);
  await submitStep(page);

  await expect(page.getByRole('alert')).toContainText('ya está inscrit');
  await expect(page.getByRole('heading', { level: 2, name: 'Inscríbete al evento' })).toBeVisible();
});

import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import { checkBaseConsents, expectReference, fillIdentityStep, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

test('inscripción feliz: completar los pasos deja una referencia LIFE-…', async ({ page }) => {
  const suffix = uniqueSuffix();
  await openEvent(page, EVENT_TITLES.servicio);
  await openRegistrationForm(page);

  await fillIdentityStep(page, { name: `Feliz Camino ${suffix}`, email: `feliz-${suffix}@example.com` });
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿En qué equipo te gustaría apoyar?' })).toBeVisible();
  await page.getByRole('radio', { name: 'Organización' }).check();
  await submitStep(page);

  await checkBaseConsents(page);
  await submitStep(page);

  const reference = await expectReference(page);
  expect(reference).toMatch(/^LIFE-[0-9A-F]{12}$/);
});

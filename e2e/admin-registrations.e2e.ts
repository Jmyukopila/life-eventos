import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import { checkBaseConsents, expectReference, fillIdentityStep, loginAsAdmin, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

test('una inscripción recién creada aparece en la lista de inscripciones del panel', async ({ page }) => {
  const suffix = uniqueSuffix();
  const identity = { name: `Panel Revisión ${suffix}`, email: `panel-revision-${suffix}@example.com` };

  await openEvent(page, EVENT_TITLES.adoracion);
  await openRegistrationForm(page);
  await fillIdentityStep(page, identity);
  await submitStep(page);
  await page.getByRole('radio', { name: 'No' }).check();
  await submitStep(page);
  await submitStep(page); // "notes" opcional
  await checkBaseConsents(page);
  await submitStep(page);
  const reference = await expectReference(page);

  await loginAsAdmin(page);
  await page.getByRole('button', { name: 'Inscripciones', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inscripciones', exact: true })).toBeVisible();

  await page.getByLabel('Buscar inscripciones por nombre o correo').fill(identity.name);
  await expect(page.getByText(identity.name)).toBeVisible();
  await expect(page.getByText(reference)).toBeVisible();
});

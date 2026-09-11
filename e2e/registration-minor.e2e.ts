import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import {
  checkBaseConsents,
  checkGuardianConsent,
  expectReference,
  fillIdentityStep,
  openEvent,
  openRegistrationForm,
  submitStep,
} from './fixtures.ts';

test('un menor de edad exige nombre, correo y autorización del representante legal', async ({ page }) => {
  const suffix = uniqueSuffix();
  await openEvent(page, EVENT_TITLES.jovenes);
  await openRegistrationForm(page);

  await page.getByLabel('Nombre completo del participante').fill(`Menor Prueba ${suffix}`);
  await page.getByLabel('Correo de contacto').fill(`menor-${suffix}@example.com`);
  await page.getByRole('checkbox', { name: 'El participante es menor de 18 años' }).check();

  // Sin datos del representante, el navegador bloquea el envío (campos required).
  await submitStep(page);
  await expect(page.getByText('Paso 1 de')).toBeVisible();

  await page.getByLabel('Nombre del representante').fill(`Representante ${suffix}`);
  await page.getByLabel('Correo del representante').fill(`representante-${suffix}@example.com`);
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Es la primera vez que nos acompañas?' })).toBeVisible();
  await page.getByRole('radio', { name: 'No' }).check();
  await submitStep(page);
  await submitStep(page); // "notes" opcional

  await checkBaseConsents(page);
  await checkGuardianConsent(page);
  await submitStep(page);

  await expectReference(page);
});

import { test, expect } from '@playwright/test';
import { EVENT_TITLES, uniqueSuffix } from './constants.ts';
import { checkBaseConsents, expectReference, fillIdentityStep, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

// Evento con el flujo condicional: responder "No" a member SALTA leader y va
// directo a availability; responder "Sí" sigue el orden lineal (leader, luego
// availability). Verificado contra events/validation.py::active_questions.

test('responder "No" salta la pregunta leader y va directo a availability', async ({ page }) => {
  const suffix = uniqueSuffix();
  await openEvent(page, EVENT_TITLES.grupos);
  await openRegistrationForm(page);
  await fillIdentityStep(page, { name: `Sin Grupo ${suffix}`, email: `sin-grupo-${suffix}@example.com` });
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Ya perteneces a un grupo de conexión?' })).toBeVisible();
  await page.getByRole('radio', { name: 'No' }).check();
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Qué horario te funciona mejor?' })).toBeVisible();
  await expect(page.getByText('¿Cómo se llama tu líder de grupo?')).toHaveCount(0);
  await page.getByLabel('¿Qué horario te funciona mejor?').selectOption('Entre semana en la noche');
  await submitStep(page);

  await checkBaseConsents(page);
  await submitStep(page);
  await expectReference(page);
});

test('responder "Sí" pasa por leader y luego por availability', async ({ page }) => {
  const suffix = uniqueSuffix();
  await openEvent(page, EVENT_TITLES.grupos);
  await openRegistrationForm(page);
  await fillIdentityStep(page, { name: `Con Grupo ${suffix}`, email: `con-grupo-${suffix}@example.com` });
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Ya perteneces a un grupo de conexión?' })).toBeVisible();
  await page.getByRole('radio', { name: 'Sí' }).check();
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Cómo se llama tu líder de grupo?' })).toBeVisible();
  await page.getByLabel('¿Cómo se llama tu líder de grupo?').fill('Líder de prueba');
  await submitStep(page);

  await expect(page.getByRole('heading', { name: '¿Qué horario te funciona mejor?' })).toBeVisible();
  await page.getByLabel('¿Qué horario te funciona mejor?').selectOption('Sábados en la mañana');
  await submitStep(page);

  await checkBaseConsents(page);
  await submitStep(page);
  await expectReference(page);
});

import { test, expect } from '@playwright/test';
import { uniqueSuffix } from './constants.ts';
import { loginAsAdmin, openEvent, openRegistrationForm, submitStep } from './fixtures.ts';

test('una pregunta agregada en el editor aparece en el formulario público del evento', async ({ page }) => {
  const suffix = uniqueSuffix();
  const title = `Evento Formulario E2E ${suffix}`;
  const questionLabel = `¿Pregunta de prueba ${suffix}?`;

  await loginAsAdmin(page);
  await page.getByRole('button', { name: 'Crear evento' }).click();
  await page.getByLabel('Nombre del evento').fill(title);
  await page.getByLabel('Estado').selectOption('published');
  await page.getByLabel('Resumen').fill('Resumen del evento con pregunta personalizada.');
  await page.getByLabel('Descripción completa').fill('Descripción del evento usado para probar el editor de formularios.');
  await page.getByLabel('Inicio *').fill('2026-12-20T10:00');
  await page.getByLabel('Lugar o dirección').fill('Casa Life · Sede E2E');
  await page.getByLabel('Cupos totales').fill('40');

  await page.getByRole('tab', { name: 'Formulario' }).click();
  await page.getByRole('button', { name: 'Agregar pregunta' }).click();
  await page.getByLabel('Título de la pregunta').fill(questionLabel);

  await page.getByRole('button', { name: 'Guardar evento' }).click();
  await expect(page.getByText('Evento guardado correctamente.')).toBeVisible();

  await openEvent(page, title);
  await openRegistrationForm(page);
  await page.getByLabel('Nombre completo del participante').fill(`Revisor Formulario ${suffix}`);
  await page.getByLabel('Correo de contacto').fill(`revisor-formulario-${suffix}@example.com`);
  await submitStep(page);

  await expect(page.getByRole('heading', { name: questionLabel })).toBeVisible();
});

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { STAFF_PASSWORD, STAFF_USERNAME } from './constants.ts';

/** Va al catálogo público y abre el detalle de un evento por su título exacto. */
export async function openEvent(page: Page, title: string) {
  await page.goto('/#/');
  await page.getByRole('link', { name: title, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
}

/** Abre el modal de inscripción ("Quiero participar") desde el detalle del evento. */
export async function openRegistrationForm(page: Page) {
  await page.getByRole('button', { name: 'Quiero participar' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
}

export interface Identity {
  name: string;
  email: string;
  phone?: string;
  minor?: boolean;
  guardianName?: string;
  guardianEmail?: string;
}

/** Completa el primer paso del formulario (datos del participante). */
export async function fillIdentityStep(page: Page, identity: Identity) {
  await page.getByLabel('Nombre completo del participante').fill(identity.name);
  await page.getByLabel('Correo de contacto').fill(identity.email);
  if (identity.phone) await page.getByLabel('Teléfono (opcional)').fill(identity.phone);
  if (identity.minor) {
    await page.getByRole('checkbox', { name: 'El participante es menor de 18 años' }).check();
    if (identity.guardianName) await page.getByLabel('Nombre del representante').fill(identity.guardianName);
    if (identity.guardianEmail) await page.getByLabel('Correo del representante').fill(identity.guardianEmail);
  }
}

/** Envía el paso actual (botón "Continuar" o "Confirmar inscripción": es el mismo botón). */
export async function submitStep(page: Page) {
  await page.getByRole('button', { name: /^(Continuar|Confirmar inscripción)$/ }).click();
}

/** Marca las tres casillas de consentimiento obligatorias del paso final (siempre presentes). */
export async function checkBaseConsents(page: Page) {
  await page.getByRole('checkbox', { name: /Confirmo que soy mayor de 18 años/ }).check();
  await page.getByRole('checkbox', { name: /He leído la política y autorizo el tratamiento/ }).check();
  await page.getByRole('checkbox', { name: /Autorizo expresamente registrar mi participación/ }).check();
}

/** Marca la cuarta casilla que solo aparece cuando el participante es menor de edad. */
export async function checkGuardianConsent(page: Page) {
  await page.getByRole('checkbox', { name: /Declaro ser el representante legal/ }).check();
}

/** Espera la pantalla de éxito y devuelve la referencia LIFE-XXXXXXXXXXXX. */
export async function expectReference(page: Page): Promise<string> {
  const reference = page.getByText(/^LIFE-[0-9A-F]{12}$/);
  await expect(reference).toBeVisible();
  return (await reference.textContent())!.trim();
}

/** Inicia sesión en el panel de administración con las credenciales de personal de prueba. */
export async function loginAsAdmin(page: Page) {
  await page.goto('/#/admin');
  await expect(page.getByRole('heading', { name: 'Bienvenido de nuevo' })).toBeVisible();
  await page.getByLabel('Usuario').fill(STAFF_USERNAME);
  await page.getByLabel('Contraseña').fill(STAFF_PASSWORD);
  await page.getByRole('button', { name: 'Ingresar al panel' }).click();
  await expect(page.getByRole('heading', { name: 'Resumen', exact: true })).toBeVisible();
}

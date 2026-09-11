// Datos fijos compartidos entre globalSetup y los specs. Nada de esto toca los
// servidores de desarrollo reales: solo existe dentro de la base de datos de prueba.
export const DJANGO_PORT = 8010;
export const VITE_PORT = 5190;
export const BASE_URL = `http://127.0.0.1:${VITE_PORT}`;

export const STAFF_USERNAME = 'e2e-panel-staff';
export const STAFF_PASSWORD = 'Iglesia-Life-2026-QA';

export const SITE_SETTINGS = {
  organization: 'Life E2E',
  contact_email: 'contacto-e2e@life.example',
  contact_phone: '3000000000',
  address: 'Calle de Pruebas 123, Bogotá',
  privacy_policy:
    'Política de tratamiento de datos personales para fines exclusivos de pruebas automatizadas. ' +
    'Life E2E recopila nombre, correo y respuestas del formulario únicamente para gestionar la inscripción ' +
    'a sus encuentros y grupos de conexión. Puedes solicitar acceso, corrección o supresión de tus datos ' +
    'escribiendo al correo de contacto registrado en esta configuración.',
  privacy_version: 'e2e-1',
  retention_days: 180,
};

export const EVENT_TITLES = {
  encuentro: 'Un encuentro que nos acerca',
  grupos: 'La vida se comparte mejor',
  jovenes: 'Una nueva generación',
  familias: 'Tiempo en familia',
  servicio: 'Manos que transforman',
  adoracion: 'Una noche. Una voz.',
} as const;

export function uniqueSuffix(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

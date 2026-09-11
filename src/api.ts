import type { ApiError, Session } from '../shared/contracts';

let csrfToken = '';
export class RequestError extends Error {
  code: string;
  fields: Record<string, string | number>;
  status: number;
  constructor(body: ApiError, status: number) {
    super(body.error.message);
    this.code = body.error.code;
    this.fields = body.error.fields ?? {};
    this.status = status;
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (options.method && options.method !== 'GET') headers.set('X-CSRFToken', csrfToken);
  let response: Response;
  try {
    response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  } catch {
    throw new Error('No pudimos conectar. Revisa tu conexión e inténtalo de nuevo.');
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new RequestError(body?.error ? body : { error: { code: 'server_error', message: 'No pudimos completar la solicitud. Inténtalo de nuevo.' } }, response.status);
  if (body?.csrfToken) csrfToken = body.csrfToken;
  if (path === '/api/logout') await session();
  return body as T;
}
export const session = () => api<Session>('/api/session');
export const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Ocurrió un error. Inténtalo de nuevo.';

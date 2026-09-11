export type Category = 'Iglesia' | 'Grupos de conexión' | 'Jóvenes' | 'Familias' | 'Servicio';
export type FieldType = 'text' | 'email' | 'tel' | 'textarea' | 'select' | 'radio' | 'date' | 'file';
export interface Rule { value: string; target: string }
export interface Question {
  id: string;
  label: string;
  type: FieldType;
  required: boolean;
  help: string;
  options: string[];
  rules: Rule[];
  accept: 'images' | 'documents' | 'both';
}
export interface Event {
  id: string;
  title: string;
  category: Category;
  summary: string;
  description: string;
  date: string;
  end_date: string | null;
  location: string;
  capacity: number;
  registered: number;
  cover: string;
  gallery: string[];
  status: 'draft' | 'published' | 'closed';
  featured: boolean;
  questions: Question[];
  form_version: number;
  created_at: string;
}
export type EventInput = Omit<Event, 'id' | 'registered' | 'form_version' | 'created_at'>;
export interface SiteSettings {
  organization: string;
  contact_email: string;
  contact_phone: string;
  address: string;
  privacy_policy: string;
  privacy_version: string;
  retention_days: number;
  registration_enabled: boolean;
  ready: boolean;
}
export interface Session { authenticated: boolean; username: string; csrfToken: string }
export interface Attachment { id: string; name: string; url: string; question_id: string }
export interface Registration {
  id: string;
  reference: string;
  event_id: string;
  event_title: string;
  created_at: string;
  name: string;
  email: string;
  phone: string;
  is_minor: boolean;
  guardian_name: string;
  guardian_email: string;
  answers: Record<string, string>;
  question_labels: Record<string, string>;
  attachments: Attachment[];
  privacy_version: string;
}
export interface RegistrationInput {
  name: string;
  email: string;
  phone: string;
  is_minor: boolean;
  guardian_name: string;
  guardian_email: string;
  guardian_consent: boolean;
  adult_confirmed: boolean;
  consent: boolean;
  sensitive_consent: boolean;
  privacy_version: string;
  form_version: number;
  request_id: string;
  answers: Record<string, string>;
}
export type OrgKind = 'organization' | 'congregation' | 'network' | 'subnetwork' | 'group';
export interface OrgNode { id: string; kind: OrgKind; name: string; parent: string | null; active: boolean }
export interface OrgNodeInput { kind: OrgKind; name: string; parent: string }
// fields lleva mensajes por campo (string) o, en el 409 `protected` de nodos, conteos (number).
export interface ApiError { error: { code: string; message: string; fields?: Record<string, string | number> } }
export interface ApiContract {
  'GET /api/session': { response: Session };
  'POST /api/login': { request: { username: string; password: string }; response: Session };
  'POST /api/logout': { response: { ok: true } };
  'GET /api/settings': { response: SiteSettings };
  'PUT /api/admin/settings': { request: Omit<SiteSettings, 'ready'>; response: SiteSettings };
  'GET /api/events': { response: { events: Event[] } };
  'GET /api/events/:id': { response: Event };
  'GET /api/admin/events': { response: { events: Event[] } };
  'POST /api/admin/events': { request: EventInput; response: Event };
  'PUT /api/admin/events/:id': { request: EventInput; response: Event };
  'POST /api/admin/images': { request: FormData; response: { url: string } };
  'GET /api/admin/nodes': { response: { nodes: OrgNode[] } };
  'POST /api/admin/nodes': { request: OrgNodeInput; response: OrgNode };
  'PUT /api/admin/nodes/:id': { request: Partial<Pick<OrgNode, 'name' | 'active'>>; response: OrgNode };
  'DELETE /api/admin/nodes/:id': { response: void };
  'POST /api/events/:id/registrations': { request: FormData; response: { reference: string; duplicate: boolean } };
  'GET /api/admin/registrations': { response: { registrations: Registration[] } };
  // Respuestas binarias: el navegador las abre o descarga, no pasan por api<T>().
  'GET /api/admin/registrations/export': { response: Blob };
  'GET /api/admin/files/:id': { response: Blob };
  'GET /media/:id': { response: Blob };
}

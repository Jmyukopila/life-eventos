import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowUpRight, CalendarDays, CheckCircle2, ChevronRight, Download, ExternalLink, Eye, ImagePlus, LayoutDashboard, LogOut, MapPin, Pencil, Plus, RefreshCw, Search, Settings, ShieldCheck, Trash2, Users } from 'lucide-react';
import type { Category, Event as ChurchEvent, EventInput, Registration, Session, SiteSettings } from '../shared/contracts';
import { api, errorMessage, json, RequestError, session } from './api';
import { Brand, ErrorNotice, formatDate, formatTime, Loading, Modal } from './ui';
import FormBuilder, { FormPreview } from './components/FormBuilder';
import { MAX_FILE_QUESTIONS, MAX_QUESTIONS, normalizeQuestions } from './formTemplates';
import './admin.css';

type Page = 'overview' | 'events' | 'registrations' | 'settings';
const pages = [
  { id: 'overview' as const, label: 'Resumen', icon: LayoutDashboard },
  { id: 'events' as const, label: 'Eventos', icon: CalendarDays },
  { id: 'registrations' as const, label: 'Inscripciones', icon: Users },
  { id: 'settings' as const, label: 'Configuración', icon: Settings },
];
const categories: Category[] = ['Iglesia', 'Grupos de conexión', 'Jóvenes', 'Familias', 'Servicio'];
const statusLabels = { draft: 'Borrador', published: 'Publicado', closed: 'Cerrado' };
const posters = [
  { name: 'Encuentro', url: '/posters/encuentro.svg' },
  { name: 'Conexión', url: '/posters/conexion.svg' },
  { name: 'Jóvenes', url: '/posters/jovenes.svg' },
  { name: 'Familias', url: '/posters/familias.svg' },
  { name: 'Servicio', url: '/posters/servicio.svg' },
  { name: 'Adoración', url: '/posters/adoracion.svg' },
];

function detailedError(error: unknown): string {
  const fields = error instanceof RequestError ? Object.entries(error.fields).map(([key, value]) => `${key}: ${value}`).join(' · ') : '';
  return `${errorMessage(error)}${fields ? ` ${fields}` : ''}`;
}

function localColombia(value: string | null): string {
  if (!value) return '';
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value));
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
}

function blankEvent(): EventInput {
  return { title: '', category: 'Iglesia', summary: '', description: '', date: '', end_date: null, location: '', capacity: 50, cover: posters[0].url, gallery: [], status: 'draft', featured: false, questions: [] };
}

function Status({ status }: { status: ChurchEvent['status'] }) {
  return <span className={`admin-badge admin-status-${status}`}>{statusLabels[status]}</span>;
}

function Login({ onLogin }: { onLogin: (value: Session) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api<Session>('/api/login', json('POST', { username: username.trim(), password }));
      if (!result.authenticated) throw new Error('No se pudo iniciar sesión. Comprueba tu acceso de personal.');
      setPassword('');
      onLogin(result);
    } catch (reason) { setError(detailedError(reason)); }
    finally { setBusy(false); }
  }
  return <div className="admin-login"><div className="admin-login-story"><Brand light/><div><span className="admin-eyebrow">Un espacio para servir</span><h1>Todo listo para<br/><em>el próximo encuentro.</em></h1><p>Organiza los eventos, acompaña las inscripciones y cuida la información de nuestra comunidad.</p></div><a href="#/" className="admin-public-link"><ArrowLeft size={18}/>Volver a los eventos</a></div><main className="admin-login-main"><form className="admin-login-form" onSubmit={submit}><div className="admin-login-mark"><ShieldCheck size={26}/></div><span className="admin-eyebrow">Administración</span><h2>Bienvenido de nuevo</h2><p>Ingresa con tu cuenta de personal autorizado.</p>{error && <ErrorNotice message={error}/>}<fieldset disabled={busy} className="admin-fieldset admin-borderless"><label className="field">Usuario<input required autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} autoFocus/></label><label className="field">Contraseña<input type="password" required autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)}/></label><button className="button primary admin-full" type="submit">{busy ? 'Iniciando sesión…' : 'Ingresar al panel'}<ArrowUpRight size={18}/></button></fieldset><p className="admin-hint">¿Necesitas acceso? Comunícate con la persona administradora de la plataforma. No hay credenciales predeterminadas.</p></form></main></div>;
}

export default function Admin() {
  const [currentSession, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const [page, setPage] = useState<Page>('overview');
  const [events, setEvents] = useState<ChurchEvent[]>([]);
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editing, setEditing] = useState<ChurchEvent | 'new' | null>(null);
  const [eventFilter, setEventFilter] = useState('');
  const [loggingOut, setLoggingOut] = useState(false);
  const requestVersion = useRef(0);

  async function checkSession() {
    setChecking(true);
    setSessionError('');
    try { setSession(await session()); }
    catch (reason) { setSessionError(detailedError(reason)); }
    finally { setChecking(false); }
  }
  useEffect(() => { void checkSession(); }, []);

  async function loadData() {
    const version = ++requestVersion.current;
    setLoading(true);
    setError('');
    try {
      const [eventData, registrationData, siteData] = await Promise.all([
        api<{ events: ChurchEvent[] }>('/api/admin/events'),
        api<{ registrations: Registration[] }>('/api/admin/registrations'),
        api<SiteSettings>('/api/settings'),
      ]);
      if (version !== requestVersion.current) return;
      setEvents(eventData.events);
      setRegistrations(registrationData.registrations);
      setSettings(siteData);
    } catch (reason) {
      if (version !== requestVersion.current) return;
      setError(reason instanceof RequestError && reason.status === 403 ? 'Acceso restringido. Este panel requiere una cuenta de personal autorizada. Si tu sesión expiró, sal y vuelve a ingresar.' : detailedError(reason));
      if (reason instanceof RequestError && reason.status === 401) setSession(null);
    } finally { if (version === requestVersion.current) setLoading(false); }
  }
  useEffect(() => {
    if (currentSession?.authenticated) void loadData();
    return () => { requestVersion.current += 1; };
  }, [currentSession?.authenticated]);

  async function logout() {
    setLoggingOut(true);
    setError('');
    try {
      await api('/api/logout', json('POST', {}));
      requestVersion.current += 1;
      setSession(null);
      setEvents([]);
      setRegistrations([]);
      setSettings(null);
      setEditing(null);
      setSuccess('');
      setPage('overview');
      await checkSession();
    } catch (reason) { setError(detailedError(reason)); }
    finally { setLoggingOut(false); }
  }
  function showRegistrations(id = '') { setEventFilter(id); setPage('registrations'); setSuccess(''); }

  return <div className="admin-app">
    {checking ? <div className="admin-initial"><Loading label="Comprobando sesión…"/></div> : sessionError ? <main className="admin-initial"><Brand/><ErrorNotice message={sessionError} retry={() => void checkSession()}/><a href="#/">Volver a la vista pública</a></main> : !currentSession?.authenticated ? <Login onLogin={setSession}/> : <div className="admin-shell">
      <aside className="admin-sidebar"><Brand light/><span className="admin-sidebar-label">Panel de administración</span><nav aria-label="Administración">{pages.map(item => <button key={item.id} type="button" className={`admin-nav-item ${page === item.id ? 'admin-nav-active' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => { setPage(item.id); setSuccess(''); }}><item.icon size={20}/><span>{item.label}</span>{page === item.id && <ChevronRight size={16}/>}</button>)}</nav><div className="admin-sidebar-bottom"><a className="admin-public-link" href="#/"><ExternalLink size={18}/>Ver sitio público</a><div className="admin-user"><div className="admin-avatar">{currentSession.username.slice(0, 1).toUpperCase()}</div><div><strong>{currentSession.username}</strong><span>Sesión de administración</span></div></div><button type="button" className="admin-logout" disabled={loggingOut} onClick={() => void logout()}><LogOut size={18}/>{loggingOut ? 'Cerrando sesión…' : 'Cerrar sesión'}</button></div></aside>
      <main className="admin-main"><header className="admin-topbar"><span>Life <span aria-hidden="true">/</span> Administración</span><a href="#/">Vista pública<ArrowUpRight size={16}/></a></header><div className="admin-content"><div className="admin-page-heading"><div><span className="admin-eyebrow">Comunidad en movimiento</span><h1>{pages.find(item => item.id === page)?.label}</h1><p>{page === 'overview' ? 'Una mirada a lo que estamos construyendo juntos.' : page === 'events' ? 'Prepara el próximo encuentro de tu comunidad.' : page === 'registrations' ? 'Cada inscripción es una persona a quien acompañar.' : 'Información institucional y cuidado de los datos.'}</p></div><div className="admin-actions"><button type="button" className="admin-icon" aria-label="Actualizar datos" disabled={loading} onClick={() => void loadData()}><RefreshCw size={19}/></button>{(page === 'events' || page === 'overview') && <button type="button" className="button primary" disabled={loading || !!error} onClick={() => setEditing('new')}><Plus size={18}/>Crear evento</button>}</div></div>
        {error && <ErrorNotice message={error} retry={() => void loadData()}/>}{success && <div className="admin-success" role="status"><CheckCircle2 size={19}/>{success}</div>}
        {loading ? <Loading label="Cargando información del panel…"/> : !error && <>
          {settings && !settings.ready && page !== 'settings' && <div className="admin-warning"><ShieldCheck size={22}/><div><strong>La recepción de inscripciones está bloqueada</strong><p>Completa y revisa la configuración institucional y de privacidad antes de habilitarla.</p></div><button className="button secondary" onClick={() => setPage('settings')}>Revisar configuración</button></div>}
          {page === 'overview' && <Overview events={events} registrations={registrations} onEdit={setEditing} onRegistrations={showRegistrations} onEvents={() => setPage('events')}/>}
          {page === 'events' && <EventsList events={events} onEdit={setEditing} onRegistrations={showRegistrations} onCreate={() => setEditing('new')}/>}
          {page === 'registrations' && <RegistrationsList registrations={registrations} events={events} eventFilter={eventFilter} setEventFilter={setEventFilter}/>}
          {page === 'settings' && settings && <SettingsEditor settings={settings} onSaved={value => { setSettings(value); setSuccess('Configuración guardada.'); }}/>}
        </>}
      </div><footer className="admin-footer">Life · Una casa para las naciones<span>Administrar también es cuidar.</span></footer></main>
    </div>}
    {editing && <EventEditor event={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={value => { setEvents(previous => previous.some(item => item.id === value.id) ? previous.map(item => item.id === value.id ? value : item) : [value, ...previous]); setEditing(null); setSuccess('Evento guardado correctamente. Las inscripciones existentes se conservan.'); }}/>} 
  </div>;
}

function Overview({ events, registrations, onEdit, onRegistrations, onEvents }: { events: ChurchEvent[]; registrations: Registration[]; onEdit: (event: ChurchEvent) => void; onRegistrations: (id?: string) => void; onEvents: () => void }) {
  const published = events.filter(event => event.status === 'published');
  const upcoming = [...events].filter(event => new Date(event.date).getTime() >= Date.now() && event.status !== 'closed').sort((a, b) => a.date.localeCompare(b.date)).slice(0, 4);
  const recent = [...registrations].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  return <><section className="admin-metrics" aria-label="Métricas"><div><span>Eventos creados</span><CalendarDays size={21}/><strong>{events.length}</strong><small>{events.filter(event => event.status === 'draft').length} en borrador</small></div><div><span>Eventos publicados</span><Eye size={21}/><strong>{published.length}</strong><small>Visibles para la comunidad</small></div><div><span>Inscripciones recibidas</span><Users size={21}/><strong>{registrations.length}</strong><small>En todos los eventos</small></div><div><span>Cupos disponibles</span><CheckCircle2 size={21}/><strong>{published.reduce((sum, event) => sum + Math.max(0, event.capacity - event.registered), 0)}</strong><small>En eventos publicados</small></div></section><div className="admin-overview-grid"><section className="admin-panel"><div className="admin-section-heading"><div><span className="admin-eyebrow">En el calendario</span><h2>Próximos encuentros</h2></div><button className="admin-text-button" onClick={onEvents}>Ver todos<ArrowUpRight size={16}/></button></div>{upcoming.length ? upcoming.map(event => <div key={event.id} className="admin-upcoming"><img src={event.cover} alt=""/><div><Status status={event.status}/><h3><button className="admin-title-button" onClick={() => onEdit(event)}>{event.title}</button></h3><p>{formatDate(event.date)} · {formatTime(event.date)}</p><button className="admin-text-button" onClick={() => onRegistrations(event.id)}>{event.registered} / {event.capacity} inscritos<ChevronRight size={15}/></button></div></div>) : <div className="admin-empty"><CalendarDays size={30}/><h3>El próximo encuentro empieza aquí</h3><p>Crea un evento y aparecerá en tu calendario.</p></div>}</section><section className="admin-panel"><div className="admin-section-heading"><div><span className="admin-eyebrow">Nuestra comunidad</span><h2>Últimas inscripciones</h2></div></div>{recent.length ? <ul className="admin-recent">{recent.map(registration => <li key={registration.id}><div className="admin-avatar">{registration.name.slice(0, 1).toUpperCase()}</div><div><strong>{registration.name}</strong><span>{registration.event_title}</span><small>{formatDate(registration.created_at)} · {formatTime(registration.created_at)}</small></div></li>)}</ul> : <div className="admin-empty"><Users size={30}/><h3>Aún no hay inscripciones</h3><p>Cuando lleguen, podrás consultarlas aquí.</p></div>}<button className="button secondary admin-full" onClick={() => onRegistrations()}>Ver inscripciones<ArrowUpRight size={17}/></button></section></div></>;
}

function EventsList({ events, onEdit, onRegistrations, onCreate }: { events: ChurchEvent[]; onEdit: (event: ChurchEvent) => void; onRegistrations: (id: string) => void; onCreate: () => void }) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const filtered = events.filter(event => event.title.toLocaleLowerCase('es').includes(search.toLocaleLowerCase('es')) && (!status || event.status === status));
  return <section><div className="admin-toolbar"><label className="admin-search"><Search size={18}/><input type="search" aria-label="Buscar eventos por título" placeholder="Buscar un evento…" value={search} onChange={event => setSearch(event.target.value)}/></label><label className="field admin-filter">Estado<select value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos los estados</option>{Object.entries(statusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><span className="admin-hint" role="status">{filtered.length} eventos</span></div>{filtered.length ? <div className="admin-event-grid">{filtered.map(event => <article className="admin-event-card" key={event.id}><div className="admin-event-cover"><img src={event.cover} alt={`Portada de ${event.title}`}/><Status status={event.status}/>{event.featured && <span className="admin-featured">Destacado</span>}</div><div className="admin-event-body"><span className="admin-eyebrow">{event.category}</span><h2>{event.title}</h2><p className="admin-event-summary">{event.summary}</p><p className="admin-meta"><CalendarDays size={16}/>{formatDate(event.date)} · {formatTime(event.date)}</p><p className="admin-meta"><MapPin size={16}/>{event.location}</p><div className="admin-capacity"><span>{event.registered} inscritos</span><span>{event.capacity} cupos</span><progress max={Math.max(event.capacity, 1)} value={event.registered} aria-label={`${event.registered} inscritos de ${event.capacity} cupos`}/></div><div className="admin-event-actions"><button className="button secondary" onClick={() => onEdit(event)}><Pencil size={16}/>Editar</button><button className="admin-text-button" onClick={() => onRegistrations(event.id)}>Inscripciones<ArrowUpRight size={16}/></button></div></div></article>)}</div> : <div className="admin-empty admin-panel"><CalendarDays size={34}/><h2>{events.length ? 'No encontramos eventos' : 'Hagamos espacio para encontrarnos'}</h2><p>{events.length ? 'Prueba otro nombre o estado.' : 'Crea tu primer evento y prepara su formulario de inscripción.'}</p>{!events.length && <button className="button primary" onClick={onCreate}><Plus size={18}/>Crear primer evento</button>}</div>}</section>;
}

function EventEditor({ event, onClose, onSaved }: { event: ChurchEvent | null; onClose: () => void; onSaved: (event: ChurchEvent) => void }) {
  const [initial] = useState<EventInput>(() => event ? { title: event.title, category: event.category, summary: event.summary, description: event.description, date: localColombia(event.date), end_date: localColombia(event.end_date) || null, location: event.location, capacity: event.capacity, cover: event.cover, gallery: [...event.gallery], status: event.status, featured: event.featured, questions: event.questions.map(question => ({ ...question, options: [...question.options], rules: [...question.rules] })) } : blankEvent());
  const [draft, setDraft] = useState(initial);
  const [tab, setTab] = useState<'publication' | 'form' | 'preview'>('publication');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [discard, setDiscard] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const update = <K extends keyof EventInput>(key: K, value: EventInput[K]) => setDraft(previous => ({ ...previous, [key]: value }));
  function close() {
    if (busy || uploading) return;
    if (JSON.stringify(initial) !== JSON.stringify(draft)) setDiscard(true);
    else onClose();
  }
  async function upload(files: FileList | null, target: 'cover' | 'gallery') {
    if (!files?.length) return;
    const selected = Array.from(files);
    setError('');
    setNotice('');
    if (target === 'gallery' && draft.gallery.length + selected.length > 8) { setError('La galería admite como máximo 8 imágenes.'); return; }
    if (selected.some(file => file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || !/\.(jpe?g|png|webp)$/i.test(file.name))) { setError('Selecciona imágenes JPG, PNG o WEBP de máximo 5 MB cada una.'); return; }
    setUploading(true);
    try {
      for (const file of selected) {
        const body = new FormData();
        body.append('file', file);
        const result = await api<{ url: string }>('/api/admin/images', { method: 'POST', body });
        setDraft(previous => ({ ...previous, ...(target === 'cover' ? { cover: result.url } : { gallery: [...previous.gallery, result.url] }) }));
      }
      setNotice('Imágenes cargadas. Guarda el evento para aplicar los cambios.');
    } catch (reason) { setError(detailedError(reason)); }
    finally { setUploading(false); }
  }
  async function save(submitEvent: FormEvent<HTMLFormElement>) {
    submitEvent.preventDefault();
    if (busy || uploading) return;
    setError('');
    setNotice('');
    const invalid = form.current?.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input:invalid, select:invalid, textarea:invalid');
    if (invalid) {
      setTab(invalid.closest('[data-panel="form"]') ? 'form' : 'publication');
      requestAnimationFrame(() => { invalid.focus(); invalid.reportValidity(); });
      return;
    }
    const questions = normalizeQuestions(draft.questions);
    const invalidQuestion = questions.find(question => !question.label.trim() || (['radio', 'select'].includes(question.type) && (question.options.length < 2 || question.options.length > 20 || question.options.some(option => option.length > 200))));
    if (invalidQuestion || questions.length > MAX_QUESTIONS || questions.filter(question => question.type === 'file').length > MAX_FILE_QUESTIONS) { setTab('form'); setError('Revisa las preguntas: cada una necesita título; las de selección requieren entre 2 y 20 opciones de máximo 200 caracteres. Máximo 40 preguntas y 3 de archivo.'); return; }
    const date = `${draft.date}:00-05:00`;
    const endDate = draft.end_date ? `${draft.end_date}:00-05:00` : null;
    if (!draft.date || !Number.isFinite(Date.parse(date)) || (endDate && (!Number.isFinite(Date.parse(endDate)) || Date.parse(endDate) <= Date.parse(date)))) { setTab('publication'); setError('La fecha de finalización debe ser posterior al inicio. Todas las horas corresponden a Colombia (UTC−05:00).'); return; }
    if (!draft.title.trim() || !draft.summary.trim() || !draft.description.trim() || !draft.location.trim()) { setTab('publication'); setError('Completa el título, resumen, descripción y lugar con texto válido.'); return; }
    if (draft.gallery.length > 8 || !Number.isInteger(draft.capacity) || draft.capacity < Math.max(1, event?.registered ?? 0)) { setTab('publication'); setError('Revisa la galería y los cupos. La capacidad no puede ser menor al número de personas inscritas.'); return; }
    setBusy(true);
    try {
      const payload: EventInput = { ...draft, title: draft.title.trim(), summary: draft.summary.trim(), description: draft.description.trim(), location: draft.location.trim(), date, end_date: endDate, questions };
      const saved = await api<ChurchEvent>(event ? `/api/admin/events/${encodeURIComponent(event.id)}` : '/api/admin/events', json(event ? 'PUT' : 'POST', payload));
      onSaved(saved);
    } catch (reason) { setError(detailedError(reason)); }
    finally { setBusy(false); }
  }
  return <Modal title={event ? 'Editar evento' : 'Crear un evento'} wide onClose={close}><div className="admin-editor"><p className="admin-hint">{event ? `Formulario versión ${event.form_version}. Los cambios no borran las inscripciones recibidas.` : 'Dale forma al encuentro. Puedes guardar un borrador antes de publicarlo.'}</p><div className="admin-tabs" role="tablist" aria-label="Editor del evento">{([{ id: 'publication', label: 'Publicación' }, { id: 'form', label: 'Formulario' }, { id: 'preview', label: 'Vista previa' }] as const).map((item, index, items) => <button type="button" id={`admin-tab-${item.id}`} role="tab" aria-selected={tab === item.id} aria-controls={`admin-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} key={item.id} onClick={() => setTab(item.id)} onKeyDown={keyEvent => { let next = index; if (keyEvent.key === 'ArrowRight') next = (index + 1) % items.length; else if (keyEvent.key === 'ArrowLeft') next = (index + items.length - 1) % items.length; else if (keyEvent.key === 'Home') next = 0; else if (keyEvent.key === 'End') next = items.length - 1; else return; keyEvent.preventDefault(); setTab(items[next].id); document.getElementById(`admin-tab-${items[next].id}`)?.focus(); }}>{item.label}</button>)}</div>
    {error && <ErrorNotice message={error}/>} {notice && <p className="admin-success" role="status">{notice}</p>}{uploading && <Loading label="Subiendo imágenes…"/>}
    <form ref={form} id="admin-event-form" onSubmit={save} noValidate><fieldset disabled={busy || uploading} className="admin-fieldset admin-borderless">
      <div role="tabpanel" id="admin-panel-publication" aria-labelledby="admin-tab-publication" data-panel="publication" hidden={tab !== 'publication'}>
        <div className="admin-section-heading"><div><h3>La información del encuentro</h3><p>Los campos indicados con * son obligatorios.</p></div><Status status={draft.status}/></div>
        <label className="field">Nombre del evento *<input required maxLength={160} value={draft.title} onChange={change => update('title', change.target.value)} placeholder="Un nombre que invite a participar"/></label>
        <div className="admin-grid-two"><label className="field">Categoría *<select value={draft.category} onChange={change => update('category', change.target.value as Category)}>{categories.map(category => <option key={category}>{category}</option>)}</select></label><label className="field">Estado *<select value={draft.status} onChange={change => update('status', change.target.value as ChurchEvent['status'])}>{Object.entries(statusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label></div>
        <p className="admin-hint">Borrador: en preparación. Publicado: visible en el sitio. Cerrado: no recibe nuevas inscripciones. La recepción también depende de la configuración institucional.</p>
        <label className="field">Resumen *<textarea required rows={2} maxLength={500} value={draft.summary} onChange={change => update('summary', change.target.value)} placeholder="La invitación que aparecerá en la tarjeta del evento"/></label>
        <label className="field">Descripción completa *<textarea required rows={5} maxLength={10000} value={draft.description} onChange={change => update('description', change.target.value)} placeholder="Qué viviremos, a quién está dirigido y qué deben saber los asistentes"/></label>
        <div className="admin-grid-two"><label className="field">Inicio *<input type="datetime-local" required value={draft.date} onChange={change => update('date', change.target.value)}/></label><label className="field">Finalización (opcional)<input type="datetime-local" value={draft.end_date ?? ''} onChange={change => update('end_date', change.target.value || null)}/></label></div>
        <p className="admin-timezone">Horario de Colombia · America/Bogota · UTC−05:00. Las fechas se guardan con el desplazamiento −05:00, sin depender de la zona horaria del equipo.</p>
        <div className="admin-grid-two"><label className="field">Lugar o dirección *<input required maxLength={300} value={draft.location} onChange={change => update('location', change.target.value)}/></label><label className="field">Cupos totales *<input required type="number" min={Math.max(1, event?.registered ?? 0)} step={1} value={Number.isNaN(draft.capacity) ? '' : draft.capacity} onChange={change => update('capacity', change.target.valueAsNumber)}/><span className="admin-hint">{event?.registered ?? 0} personas inscritas actualmente.</span></label></div>
        <label className="admin-check"><input type="checkbox" checked={draft.featured} onChange={change => update('featured', change.target.checked)}/>Destacar en la vista pública</label>
        <section className="admin-media-editor"><div className="admin-section-heading"><div><h3>Portada del evento</h3><p>Elige una portada de demostración o carga una propia.</p></div></div><img className="admin-cover-preview" src={draft.cover} alt="Portada seleccionada"/><div className="admin-poster-options">{posters.map(poster => <button type="button" className={`admin-poster ${draft.cover === poster.url ? 'admin-poster-selected' : ''}`} key={poster.url} aria-pressed={draft.cover === poster.url} onClick={() => update('cover', poster.url)}><img src={poster.url} alt=""/><span>{poster.name}</span></button>)}</div><label className="field admin-upload"><span><ImagePlus size={18}/>Subir portada</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={change => { void upload(change.target.files, 'cover'); change.target.value = ''; }}/><span className="admin-hint">JPG, PNG o WEBP · máximo 5 MB.</span></label></section>
        <section className="admin-media-editor"><div className="admin-section-heading"><div><h3>Galería <span className="admin-optional">{draft.gallery.length} / 8</span></h3><p>Las imágenes de portada y galería serán públicas. No subas documentos personales.</p></div></div><div className="admin-gallery">{draft.gallery.map((url, index) => <div key={`${url}-${index}`}><img src={url} alt={`Imagen de galería ${index + 1}`}/><button type="button" className="admin-icon admin-danger" aria-label={`Quitar imagen ${index + 1} de la galería`} onClick={() => update('gallery', draft.gallery.filter((_, position) => position !== index))}><Trash2 size={16}/></button></div>)}</div><label className="field admin-upload">Agregar imágenes<input type="file" multiple disabled={draft.gallery.length >= 8 || uploading || busy} accept="image/jpeg,image/png,image/webp" onChange={change => { void upload(change.target.files, 'gallery'); change.target.value = ''; }}/><span className="admin-hint">Hasta 8 imágenes. Máximo 5 MB por archivo.</span></label></section>
      </div>
      <div role="tabpanel" id="admin-panel-form" aria-labelledby="admin-tab-form" data-panel="form" hidden={tab !== 'form'}><FormBuilder questions={draft.questions} onChange={questions => update('questions', questions)}/></div>
    </fieldset></form>
    {tab === 'preview' && <div role="tabpanel" id="admin-panel-preview" aria-labelledby="admin-tab-preview"><article className="admin-event-preview"><img src={draft.cover} alt="Vista previa de portada"/><span className="admin-eyebrow">{draft.category}</span><h2>{draft.title || 'El nombre de tu evento'}</h2><p className="admin-preview-lead">{draft.summary || 'Aquí aparecerá la invitación al encuentro.'}</p><p className="admin-meta"><CalendarDays size={17}/>{draft.date ? `${formatDate(`${draft.date}:00-05:00`)} · ${formatTime(`${draft.date}:00-05:00`)}` : 'Fecha por definir'} · Colombia</p><p className="admin-meta"><MapPin size={17}/>{draft.location || 'Lugar por definir'}</p><p className="admin-preserve">{draft.description}</p>{draft.gallery.length > 0 && <div className="admin-gallery">{draft.gallery.map((url, index) => <img key={`${url}-${index}`} src={url} alt={`Galería ${index + 1}`}/>)}</div>}</article><FormPreview questions={normalizeQuestions(draft.questions)}/></div>}
    <div className="admin-editor-footer"><span className="admin-hint">{draft.status === 'draft' ? 'El borrador no será visible en el sitio.' : 'Guardar aplicará los cambios al evento.'}</span><div className="admin-actions"><button className="button secondary" type="button" onClick={close} disabled={busy || uploading}>Cancelar</button><button className="button primary" type="submit" form="admin-event-form" disabled={busy || uploading}>{busy ? 'Guardando…' : draft.status === 'draft' ? 'Guardar borrador' : 'Guardar evento'}</button></div></div>
  </div>{discard && <Modal title="¿Descartar cambios sin guardar?" onClose={() => setDiscard(false)}><div className="admin-confirm"><p>Los cambios de este borrador no se aplicarán. Las inscripciones existentes no se modificarán.</p><div className="admin-actions"><button className="button secondary" onClick={() => setDiscard(false)}>Seguir editando</button><button className="button primary" onClick={onClose}>Descartar cambios</button></div></div></Modal>}</Modal>;
}

function RegistrationsList({ registrations, events, eventFilter, setEventFilter }: { registrations: Registration[]; events: ChurchEvent[]; eventFilter: string; setEventFilter: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Registration | null>(null);
  const term = search.trim().toLocaleLowerCase('es');
  const filtered = registrations.filter(registration => (!eventFilter || registration.event_id === eventFilter) && `${registration.name} ${registration.email}`.toLocaleLowerCase('es').includes(term));
  const csv = `/api/admin/registrations/export${eventFilter ? `?event_id=${encodeURIComponent(eventFilter)}` : ''}`;
  return <section><div className="admin-toolbar"><label className="admin-search"><Search size={18}/><input type="search" aria-label="Buscar inscripciones por nombre o correo" placeholder="Buscar nombre o correo…" value={search} onChange={event => setSearch(event.target.value)}/></label><label className="field admin-filter">Evento<select value={eventFilter} onChange={event => setEventFilter(event.target.value)}><option value="">Todos los eventos</option>{events.map(event => <option value={event.id} key={event.id}>{event.title}</option>)}</select></label><a className="button secondary" href={csv}><Download size={17}/>Exportar CSV</a></div><div className="admin-section-heading"><p role="status">{filtered.length} inscripciones{term && ' coinciden con la búsqueda'}</p><p className="admin-hint">El CSV incluye todo el evento seleccionado, no la búsqueda por texto. Contiene datos personales.</p></div>{filtered.length ? <div className="admin-table-wrap"><table className="admin-table"><caption className="admin-sr-only">Inscripciones recibidas</caption><thead><tr><th scope="col">Persona</th><th scope="col">Evento</th><th scope="col">Fecha</th><th scope="col">Referencia</th><th scope="col"><span className="admin-sr-only">Acciones</span></th></tr></thead><tbody>{filtered.map(registration => <tr key={registration.id}><td><strong>{registration.name}</strong><span>{registration.email}</span></td><td>{registration.event_title}</td><td>{formatDate(registration.created_at)}<span>{formatTime(registration.created_at)}</span></td><td><code>{registration.reference}</code></td><td><button className="button secondary" aria-label={`Ver inscripción de ${registration.name}`} onClick={() => setSelected(registration)}><Eye size={16}/>Ver detalle</button></td></tr>)}</tbody></table></div> : <div className="admin-empty admin-panel"><Users size={34}/><h2>No hay inscripciones para mostrar</h2><p>{search || eventFilter ? 'Cambia la búsqueda o el filtro de evento.' : 'Las nuevas inscripciones aparecerán aquí cuando la comunidad empiece a participar.'}</p></div>}{selected && <RegistrationDetail registration={selected} onClose={() => setSelected(null)}/>}</section>;
}

function RegistrationDetail({ registration: value, onClose }: { registration: Registration; onClose: () => void }) {
  const ids = [...new Set([...Object.keys(value.question_labels), ...Object.keys(value.answers), ...value.attachments.map(attachment => attachment.question_id)])];
  return <Modal title="Detalle de inscripción" wide onClose={onClose}><div className="admin-registration-detail"><span className="admin-eyebrow">{value.reference}</span><h3>{value.name}</h3><p>{value.event_title} · {formatDate(value.created_at, { year: 'numeric' })} · {formatTime(value.created_at)}</p><dl className="admin-detail-grid"><div><dt>Correo</dt><dd><a href={`mailto:${value.email}`}>{value.email}</a></dd></div><div><dt>Teléfono</dt><dd>{value.phone || 'No indicado'}</dd></div><div><dt>Menor de edad</dt><dd>{value.is_minor ? 'Sí' : 'No'}</dd></div><div><dt>Versión de privacidad aceptada</dt><dd>{value.privacy_version}</dd></div>{value.is_minor && <><div><dt>Acudiente</dt><dd>{value.guardian_name}</dd></div><div><dt>Correo del acudiente</dt><dd>{value.guardian_email}</dd></div></>}</dl><h4>Respuestas del formulario original</h4><p className="admin-hint">Los títulos corresponden a la versión respondida, aunque el evento haya cambiado.</p><dl className="admin-answer-list">{ids.map(id => <div key={id}><dt>{value.question_labels[id] || 'Pregunta del formulario original'}</dt><dd>{value.answers[id] || (value.attachments.some(attachment => attachment.question_id === id) ? 'Archivo adjunto' : 'Sin respuesta')}{value.attachments.filter(attachment => attachment.question_id === id).map(attachment => <a className="admin-attachment" key={attachment.id} href={attachment.url} target="_blank" rel="noopener noreferrer"><Download size={17}/>{attachment.name}<span className="admin-hint">Acceso privado · personal autorizado</span></a>)}</dd></div>)}</dl>{!ids.length && <p>No se solicitaron respuestas adicionales.</p>}<div className="admin-note"><ShieldCheck size={21}/><p>Información personal de acceso restringido. No compartas archivos ni exportaciones fuera del personal autorizado.</p></div><button className="button secondary" onClick={onClose}>Cerrar detalle</button></div></Modal>;
}

function SettingsEditor({ settings, onSaved }: { settings: SiteSettings; onSaved: (settings: SiteSettings) => void }) {
  const [draft, setDraft] = useState(settings);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  useEffect(() => { setDraft(settings); }, [settings]);
  const update = <K extends keyof SiteSettings>(key: K, value: SiteSettings[K]) => { setDraft(previous => ({ ...previous, [key]: value })); setSuccess(''); };
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const { ready: _ready, ...payload } = draft;
      const saved = await api<SiteSettings>('/api/admin/settings', json('PUT', payload));
      setDraft(saved);
      onSaved(saved);
      setSuccess(saved.ready ? 'Configuración guardada. El servidor confirma que la recepción está habilitada.' : 'Configuración guardada. La recepción permanece bloqueada; revisa los datos obligatorios y la habilitación.');
    } catch (reason) { setError(detailedError(reason)); }
    finally { setBusy(false); }
  }
  return <form className="admin-settings" onSubmit={save}>{error && <ErrorNotice message={error}/>} {success && <p className="admin-success" role="status">{success}</p>}<div className={settings.ready ? 'admin-note' : 'admin-warning'}><ShieldCheck size={24}/><div><strong>{settings.ready ? 'Recepción de inscripciones habilitada' : 'Recepción de inscripciones bloqueada'}</strong><p>El servidor solo permite recibir inscripciones cuando la configuración está completa y habilitada (ready). Guardar datos no equivale a una revisión jurídica.</p></div></div><fieldset className="admin-fieldset admin-borderless" disabled={busy}><section className="admin-panel"><div className="admin-section-heading"><div><span className="admin-eyebrow">01 · Responsable</span><h2>Información de la organización</h2><p>Datos reales del responsable del tratamiento de datos personales.</p></div></div><label className="field">Nombre o razón social del responsable *<input required maxLength={200} value={draft.organization} onChange={event => update('organization', event.target.value)}/></label><div className="admin-grid-two"><label className="field">Correo de contacto *<input type="email" required value={draft.contact_email} onChange={event => update('contact_email', event.target.value)}/></label><label className="field">Teléfono de contacto *<input type="tel" required value={draft.contact_phone} onChange={event => update('contact_phone', event.target.value)}/></label></div><label className="field">Dirección del responsable *<input required value={draft.address} onChange={event => update('address', event.target.value)}/></label></section><section className="admin-panel"><div className="admin-section-heading"><div><span className="admin-eyebrow">02 · Privacidad</span><h2>Cuidado de los datos personales</h2><p>Usa la política aprobada para tu organización; no un texto de ejemplo.</p></div></div><div className="admin-note"><div><strong>Requiere revisión legal real</strong><p>La política y las autorizaciones deben revisarse por el responsable y asesoría competente, incluyendo datos sensibles de carácter religioso, menores de edad, finalidades, derechos y canales de atención. Esta plataforma no certifica cumplimiento legal ni sustituye esa revisión.</p></div></div><label className="field">Texto de la política de privacidad *<textarea required rows={12} value={draft.privacy_policy} onChange={event => update('privacy_policy', event.target.value)} placeholder="Pega aquí la política real revisada y aprobada por tu organización."/></label><div className="admin-grid-two"><label className="field">Versión de la política *<input required maxLength={100} value={draft.privacy_version} onChange={event => update('privacy_version', event.target.value)}/><span className="admin-hint">Actualiza esta versión cuando cambie la política. Se conserva en cada inscripción.</span></label><label className="field">Plazo de conservación en días *<input type="number" required min={1} step={1} value={Number.isNaN(draft.retention_days) ? '' : draft.retention_days} onChange={event => update('retention_days', event.target.valueAsNumber)}/><span className="admin-hint">Define el plazo aprobado para las finalidades reales. Este panel no elimina datos ni acredita una eliminación automática.</span></label></div></section><section className="admin-panel"><span className="admin-eyebrow">03 · Recepción</span><h2>Habilitar las inscripciones</h2><label className="admin-check admin-enable"><input type="checkbox" checked={draft.registration_enabled} onChange={event => update('registration_enabled', event.target.checked)}/><span>Permitir nuevas inscripciones una vez completada y revisada la configuración</span></label><p className="admin-hint">Desactivar esta opción bloquea nuevas solicitudes sin borrar las ya recibidas. El estado definitivo lo calcula el servidor al guardar.</p></section><div className="admin-settings-footer"><span className="admin-hint">* Campos obligatorios</span><button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar configuración'}</button></div></fieldset></form>;
}

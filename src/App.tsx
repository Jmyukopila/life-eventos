import { lazy, Suspense, useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown, Heart, MapPin, Menu, Search, ShieldCheck, SlidersHorizontal, Users, X } from 'lucide-react';
import type { Category, Event, SiteSettings } from '../shared/contracts';
import { api, errorMessage, session } from './api';
import { Brand, ErrorNotice, formatDate, formatTime, Loading, Modal } from './ui';
import RegistrationForm, { Privacy } from './RegistrationForm';

const Admin = lazy(() => import('./Admin'));
const categories: Category[] = ['Iglesia', 'Grupos de conexión', 'Jóvenes', 'Familias', 'Servicio'];

function useRoute() {
  const [route, setRoute] = useState(window.location.hash.slice(1) || '/');
  useEffect(() => {
    const change = () => { setRoute(window.location.hash.slice(1) || '/'); window.scrollTo({ top: 0 }); };
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  return route;
}

function Header({ onAbout }: { onAbout: () => void }) {
  const [menu, setMenu] = useState(false);
  return <header className="site-header"><div className="header-inner"><Brand/><nav aria-label="Navegación principal" className={menu ? 'main-nav open' : 'main-nav'}><a href="#/" className="nav-active" onClick={() => setMenu(false)}>Encuentros</a><a href="#/grupos" onClick={() => setMenu(false)}>Grupos de conexión</a><button onClick={() => { onAbout(); setMenu(false); }}>Nuestra casa <ArrowUpRight size={14}/></button></nav><a href="#/admin" className="admin-link"><ShieldCheck size={16}/><span>Administración</span></a><button className="icon-button menu-toggle" aria-label={menu ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X/> : <Menu/>}</button></div></header>;
}

function EventCard({ event }: { event: Event }) {
  const closed = event.status === 'closed' || new Date(event.date) <= new Date();
  const full = event.registered >= event.capacity;
  return <article className="event-card"><a href={`#/evento/${event.id}`} className="poster-link" aria-label={`Ver ${event.title}`}><img src={event.cover} alt={`Cartel de ${event.title}`} loading="lazy"/><span className="poster-arrow"><ArrowUpRight size={22}/></span>{closed || full ? <span className="poster-status">{closed ? 'Inscripciones cerradas' : 'Cupos completos'}</span> : null}</a><div className="card-meta"><span className={`category-label category-${categories.indexOf(event.category)}`}>{event.category}</span><span className="free-label">Entrada libre</span></div><h3><a href={`#/evento/${event.id}`}>{event.title}</a></h3><p>{event.summary}</p><div className="card-details"><span><CalendarDays size={15}/>{formatDate(event.date, { month: 'short' })} · {formatTime(event.date)}</span><span><MapPin size={15}/>{event.location.split(' · ')[0]}</span></div></article>;
}

function Catalog({ events, groupsOnly }: { events: Event[]; groupsOnly: boolean }) {
  const [category, setCategory] = useState('Todos');
  const [search, setSearch] = useState('');
  const [period, setPeriod] = useState('all');
  useEffect(() => { setCategory(groupsOnly ? 'Grupos de conexión' : 'Todos'); }, [groupsOnly]);
  const now = new Date();
  const upcoming = events.filter(event => event.status === 'published' && new Date(event.date) > now);
  const featured = upcoming.find(event => event.featured) || upcoming[0];
  const filtered = events.filter(event => {
    const date = new Date(event.date);
    const matching = `${event.title} ${event.summary} ${event.category} ${event.location}`.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().includes(search.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase());
    const month = formatDate(event.date, { month: 'numeric', year: 'numeric', day: undefined }) === formatDate(now.toISOString(), { month: 'numeric', year: 'numeric', day: undefined });
    return matching && (category === 'Todos' || category === event.category) && (period === 'all' ? date > now : period === 'month' ? month && date > now : date <= now);
  }).sort((a, b) => period === 'past' ? Date.parse(b.date) - Date.parse(a.date) : Date.parse(a.date) - Date.parse(b.date));
  function scrollCatalog() { document.getElementById('encuentros')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); }
  return <><section className="hero"><div className="hero-inner"><div className="hero-copy"><div className="eyebrow"><span className="live-dot"/>Somos Life. Somos familia.</div><h1>Hay un lugar<br/><em>para ti.</em></h1><p>La fe se vive mejor cuando la compartimos.<br className="desktop-break"/> Encuentra tu próximo encuentro y ven a ser parte.</p><button className="button primary hero-button" onClick={scrollCatalog}>Encuentra tu próximo evento <ArrowDownIcon/></button><div className="hero-footnote"><span className="little-mark"><Heart size={18}/></span><span>Una casa abierta.<br/><strong>Una comunidad que te espera.</strong></span></div></div>{featured ? <a className="hero-feature" href={`#/evento/${featured.id}`}><div className="featured-art"><img src={featured.cover} alt={`Cartel de ${featured.title}`}/><span className="featured-label"><span/>Nuestro próximo gran encuentro</span></div><div className="featured-caption"><div className="date-tile"><strong>{formatDate(featured.date, { day: '2-digit', month: undefined })}</strong><span>{formatDate(featured.date, { month: 'short', day: undefined }).replace('.', '')}</span></div><div className="feature-caption-text"><h2>{featured.title}</h2><span>{formatTime(featured.date)} <span aria-hidden="true">·</span> {featured.location.split(' · ')[0]}</span></div><span className="feature-link"><ArrowUpRight size={24}/></span></div></a> : <div className="hero-empty"><Brand light/><p>Estamos preparando<br/>nuestros próximos encuentros.</p></div>}</div></section><div className="community-strip"><div className="container strip-inner"><span><Users size={18}/><strong>Juntos hacemos casa.</strong></span><span>Para todas las edades y cada etapa de la vida.</span><a href="#/grupos">Conoce los grupos de conexión <ArrowRight size={16}/></a></div></div><section className="catalog container" id="encuentros"><div className="section-heading"><div><p className="eyebrow">Comparte. Conecta. Crece.</p><h2>{groupsOnly ? 'Encuentra tu comunidad' : 'Nos encontramos aquí'}</h2></div><p>Haz espacio en tu agenda.<br/>Lo que viene, lo vivimos juntos.</p></div><div className="catalog-tools"><div className="category-filters" aria-label="Filtrar por categoría">{['Todos', ...categories].map(item => <button key={item} aria-pressed={category === item} className={category === item ? 'filter active' : 'filter'} onClick={() => setCategory(item)}>{item === 'Todos' && <SlidersHorizontal size={14}/>} {item}</button>)}</div><div className="search-box"><Search size={18}/><input aria-label="Buscar eventos" placeholder="Busca un encuentro…" value={search} onChange={e => setSearch(e.target.value)}/>{search && <button className="icon-button" aria-label="Limpiar búsqueda" onClick={() => setSearch('')}><X size={16}/></button>}</div></div><div className="catalog-summary"><span aria-live="polite">{filtered.length} {filtered.length === 1 ? 'encuentro para ti' : 'encuentros para ti'}</span><label className="period-select"><CalendarDays size={15}/><select aria-label="Filtrar por fecha" value={period} onChange={e => setPeriod(e.target.value)}><option value="all">Próximos eventos</option><option value="month">Este mes</option><option value="past">Eventos anteriores</option></select><ChevronDown size={14}/></label></div>{filtered.length ? <div className="event-grid">{filtered.map(event => <EventCard key={event.id} event={event}/>)}</div> : <div className="empty-state"><Search size={32}/><h3>No hay encuentros con estos filtros</h3><p>Prueba otra búsqueda o consulta todos los próximos eventos.</p><button className="button secondary" onClick={() => { setSearch(''); setCategory('Todos'); setPeriod('all'); }}>Ver todos los encuentros</button></div>}<div className="connection-banner"><div className="connection-graphic" aria-hidden="true"><span/><span/><span/></div><div><span className="eyebrow">La iglesia también sucede entre semana</span><h2>Una mesa. Una conversación.<br/><em>Un grupo para ti.</em></h2><p>Conoce personas con quienes compartir la vida y crecer en la fe.</p></div><a className="button light" href="#/grupos" onClick={() => { setCategory('Grupos de conexión'); if (groupsOnly) scrollCatalog(); }}>Explorar grupos <ArrowUpRight size={18}/></a></div></section></>;
}

function ArrowDownIcon() { return <ArrowRight size={18} className="arrow-down"/>; }

function EventDetail({ id, settings, refresh }: { id: string; settings: SiteSettings; refresh: () => void }) {
  const [event, setEvent] = useState<Event | null>(null);
  const [error, setError] = useState('');
  const [register, setRegister] = useState(false);
  const [lightbox, setLightbox] = useState('');
  const [copied, setCopied] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => { let mounted = true; setError(''); api<Event>(`/api/events/${encodeURIComponent(id)}`).then(data => { if (mounted) setEvent(data); }).catch(cause => { if (mounted) setError(errorMessage(cause)); }); return () => { mounted = false; }; }, [id, revision]);
  useEffect(() => { if (event) document.title = `${event.title} · Life`; }, [event]);
  if (error) return <main className="container page-content"><a href="#/" className="back-link"><ArrowLeft size={16}/>Todos los encuentros</a><ErrorNotice message={error} retry={() => setRevision(revision + 1)}/></main>;
  if (!event) return <Loading label="Buscando tu próximo encuentro…"/>;
  const closed = event.status !== 'published' || new Date(event.date) <= new Date();
  const full = event.registered >= event.capacity;
  async function share() { try { await navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2500); } catch { setCopied(false); } }
  return <main className="container event-detail"><a href="#/" className="back-link"><ArrowLeft size={16}/>Todos los encuentros</a><div className="detail-heading"><span className="category-label">{event.category}</span><h1>{event.title}</h1><p>{event.summary}</p></div><div className="detail-grid"><div className="detail-story"><button className="detail-image" onClick={() => setLightbox(event.cover)} aria-label="Ampliar cartel del evento"><img src={event.cover} alt={`Cartel de ${event.title}`}/></button><section className="about-event"><h2>Un poco más sobre este encuentro</h2><div className="preserve-lines">{event.description}</div></section>{event.gallery.length > 0 && <section className="gallery-section"><h2>Conoce el encuentro</h2><div className="gallery-grid">{event.gallery.map((image, i) => <button key={`${image}-${i}`} onClick={() => setLightbox(image)} aria-label={`Ampliar imagen ${i + 1}`}><img src={image} alt={`Galería de ${event.title}, imagen ${i + 1}`} loading="lazy"/></button>)}</div></section>}<div className="event-host"><span className="host-icon"><Heart size={22}/></span><div><strong>Organizado por Life</strong><p>Una casa para las naciones</p></div><button className="text-button" onClick={share}>{copied ? <><Check size={16}/>Enlace copiado</> : <>Compartir <ArrowUpRight size={16}/></>}</button></div></div><aside className="registration-card"><div className="registration-card-top"><span>Ven a ser parte</span><strong>Entrada libre</strong></div><ul className="event-facts"><li><CalendarDays/><div><strong>{formatDate(event.date, { weekday: 'long' })}</strong><span>{formatTime(event.date)} · Hora de Colombia</span></div></li><li><MapPin/><div><strong>{event.location}</strong><span>Encuentro presencial</span></div></li><li><Users/><div><strong>{closed ? 'Inscripciones cerradas' : full ? 'Cupos completos' : `${event.capacity - event.registered} cupos disponibles`}</strong><span>Un registro por participante</span></div></li></ul><button className="button primary" disabled={closed || full || !settings.ready} onClick={() => setRegister(true)}>{closed ? 'Inscripciones cerradas' : full ? 'Cupos completos' : !settings.ready ? 'Inscripciones próximamente' : 'Quiero participar'}<ArrowRight size={18}/></button>{!settings.ready && !closed && <p className="registration-hint">La iglesia está preparando las inscripciones. Por ahora puedes conocer los encuentros.</p>}<p className="secure-note"><ShieldCheck size={15}/>Tus datos y archivos son privados</p><div className="questions-contact"><strong>¿Tienes alguna pregunta?</strong>{settings.contact_email ? <a href={`mailto:${settings.contact_email}`}>Escríbenos <ArrowUpRight size={14}/></a> : <p>Consulta con el equipo de bienvenida de Life.</p>}</div></aside></div>{register && <RegistrationForm event={event} settings={settings} onClose={() => setRegister(false)} onSuccess={() => { setRevision(value => value + 1); refresh(); }}/ >}{lightbox && <Modal title="Galería del evento" wide onClose={() => setLightbox('')}><img className="lightbox-image" src={lightbox} alt={event.title}/></Modal>}</main>;
}

export default function App() {
  const route = useRoute();
  const [events, setEvents] = useState<Event[]>([]);
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [about, setAbout] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    setError('');
    Promise.all([api<{ events: Event[] }>('/api/events'), api<SiteSettings>('/api/settings'), session()]).then(([data, config]) => { if (alive) { setEvents(data.events); setSettings(config); } }).catch(cause => { if (alive) setError(errorMessage(cause)); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [revision, route === '/admin']);
  useEffect(() => { if (!route.startsWith('/evento/')) document.title = route === '/admin' ? 'Administración · Life' : 'Life · Encuentros que nos acercan'; }, [route]);
  if (route === '/admin') return <Suspense fallback={<Loading/>}><Admin/></Suspense>;
  return <><a href="#contenido" className="skip-link" onClick={e => { e.preventDefault(); document.getElementById('contenido')?.focus(); }}>Saltar al contenido</a><Header onAbout={() => setAbout(true)}/><div id="contenido" tabIndex={-1}>{loading ? <Loading label="Preparando los encuentros…"/> : error ? <div className="container page-content"><ErrorNotice message={error} retry={() => { setLoading(true); setRevision(value => value + 1); }}/></div> : route.startsWith('/evento/') && settings ? <EventDetail key={route} id={route.split('/')[2]} settings={settings} refresh={() => setRevision(value => value + 1)}/> : route === '/' || route === '/grupos' ? <main><Catalog events={events} groupsOnly={route === '/grupos'}/></main> : <main className="container page-content"><h1>No encontramos esta página</h1><a className="button primary" href="#/">Volver a los encuentros</a></main>}</div><footer className="site-footer"><div className="container footer-main"><Brand light/><p>Vivimos la fe.<br/>Compartimos la vida.</p><div><strong>Sigamos en contacto</strong>{settings?.contact_email ? <a href={`mailto:${settings.contact_email}`}>{settings.contact_email} <ArrowUpRight size={14}/></a> : <span>Te esperamos en nuestra casa.</span>}</div></div><div className="container footer-bottom"><span>© {new Date().getFullYear()} Life. Una casa para las naciones.</span><button onClick={() => setPrivacy(true)}>Privacidad y tratamiento de datos</button><span>Hecho para encontrarnos.</span></div></footer>{about && <Modal title="Nuestra casa" onClose={() => setAbout(false)}><div className="modal-body"><Brand/><h3>Hay un lugar para ti en Life.</h3><p>Una casa para las naciones. Aquí encontrarás los encuentros de nuestra iglesia y los espacios para compartir en grupos de conexión.</p><p>Si es tu primera vez, el equipo de bienvenida puede orientarte. No necesitas pertenecer a un grupo para conocer nuestros eventos.</p>{settings?.address && <p><MapPin size={16}/> {settings.address}</p>}<button className="button primary" onClick={() => setAbout(false)}>Conocer los encuentros <ArrowRight size={17}/></button></div></Modal>}{privacy && settings && <Privacy settings={settings} onClose={() => setPrivacy(false)}/>}</>;
}

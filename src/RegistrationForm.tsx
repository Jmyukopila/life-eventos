import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Download, FileUp, ShieldCheck, X } from 'lucide-react';
import type { Event, Question, RegistrationInput, SiteSettings } from '../shared/contracts';
import { api, errorMessage, RequestError } from './api';
import { activeQuestions, pruneAnswers, validateQuestion } from './flow';
import { formatDate, Modal } from './ui';

export function Privacy({ settings, onClose }: { settings: SiteSettings; onClose: () => void }) {
  return <Modal title="Tratamiento de datos personales" onClose={onClose}><div className="modal-body policy"><p className="muted">Responsable: {settings.organization} · Versión {settings.privacy_version}</p>{settings.privacy_policy ? <div className="preserve-lines">{settings.privacy_policy}</div> : <p>La iglesia aún debe publicar su política de tratamiento de datos. Las inscripciones permanecerán deshabilitadas hasta que esté configurada.</p>}{settings.contact_email && <p>Para consultar, corregir o solicitar la supresión de tus datos: <a href={`mailto:${settings.contact_email}`}>{settings.contact_email}</a>.</p>}<button className="button secondary" onClick={onClose}>Entendido</button></div></Modal>;
}

export function QuestionInput({ question, value, file, onChange, onFile }: { question: Question; value: string; file?: File; onChange: (value: string) => void; onFile: (file?: File) => void }) {
  const id = `q-${question.id}`;
  const common = { id, value, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onChange(event.target.value), 'aria-label': question.label, 'aria-describedby': question.help ? `${id}-help` : undefined };
  return <div className="question-input">{question.help && <p id={`${id}-help`} className="muted">{question.help}</p>}{question.type === 'radio' ? <div className="radio-options">{question.options.map(option => <label key={option} className={value === option ? 'radio-option selected' : 'radio-option'}><input type="radio" name={id} checked={value === option} onChange={() => onChange(option)}/><span>{option}</span>{value === option && <Check size={18}/>}</label>)}</div> : question.type === 'select' ? <select {...common}><option value="">Selecciona una opción</option>{question.options.map(option => <option key={option}>{option}</option>)}</select> : question.type === 'textarea' ? <textarea {...common} rows={4} maxLength={4000} placeholder="Escribe tu respuesta…"/> : question.type === 'file' ? <div className="file-zone"><FileUp size={28}/><strong>{file ? file.name : 'Selecciona tu archivo'}</strong><span className="muted">{question.accept === 'images' ? 'JPG, PNG o WebP' : question.accept === 'documents' ? 'PDF' : 'JPG, PNG, WebP o PDF'} · Máximo 5 MB</span><input id={id} aria-label={question.label} type="file" accept={question.accept === 'images' ? '.jpg,.jpeg,.png,.webp' : question.accept === 'documents' ? '.pdf' : '.jpg,.jpeg,.png,.webp,.pdf'} onChange={event => onFile(event.target.files?.[0])}/>{file && <button type="button" className="text-button" onClick={() => onFile(undefined)}><X size={14}/>Quitar archivo</button>}</div> : <input {...common} type={question.type} maxLength={4000} placeholder={question.type === 'date' ? undefined : 'Escribe tu respuesta…'}/>}</div>;
}

function calendarFile(event: Event) {
  const date = (value: string) => new Date(value).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  const escape = (value: string) => value.replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
  const content = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Life//Eventos//ES', 'BEGIN:VEVENT', `UID:${event.id}@life.local`, `DTSTAMP:${date(new Date().toISOString())}`, `DTSTART:${date(event.date)}`, `DTEND:${date(event.end_date || new Date(new Date(event.date).getTime() + 7200000).toISOString())}`, `SUMMARY:${escape(event.title)}`, `LOCATION:${escape(event.location)}`, 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
  const url = URL.createObjectURL(new Blob([content], { type: 'text/calendar;charset=utf-8' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'evento-life.ics'; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function RegistrationForm({ event, settings, onClose, onSuccess }: { event: Event; settings: SiteSettings; onClose: () => void; onSuccess: () => void }) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<Record<string, File>>({});
  const [identity, setIdentity] = useState({ name: '', email: '', phone: '', is_minor: false, guardian_name: '', guardian_email: '' });
  const [consents, setConsents] = useState({ adult_confirmed: false, consent: false, sensitive_consent: false, guardian_consent: false });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reference, setReference] = useState('');
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [requestId] = useState(() => crypto.randomUUID());
  const path = activeQuestions(event.questions, answers);
  const question = step > 0 && step <= path.length ? path[step - 1] : null;
  const isConsent = step > path.length;
  const total = path.length + 2;
  function updateAnswer(id: string, value: string) {
    const next = pruneAnswers(event.questions, { ...answers, [id]: value });
    const active = new Set(activeQuestions(event.questions, next).map(item => item.id));
    setAnswers(next);
    setFiles(current => Object.fromEntries(Object.entries(current).filter(([key]) => active.has(key))));
    setError('');
  }
  async function next(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (question) {
      const message = validateQuestion(question, answers[question.id] || '', files[question.id]);
      if (message) { setError(message); return; }
    }
    if (!isConsent) { setStep(current => current + 1); return; }
    setBusy(true);
    const data: RegistrationInput = { ...identity, ...consents, answers: pruneAnswers(event.questions, answers), form_version: event.form_version, privacy_version: settings.privacy_version, request_id: requestId };
    const payload = new FormData(); payload.append('data', JSON.stringify(data));
    Object.entries(files).forEach(([id, file]) => { if (path.some(q => q.id === id && q.type === 'file')) payload.append(`file_${id}`, file); });
    try {
      const response = await api<{ reference: string }>('/api/events/' + event.id + '/registrations', { method: 'POST', body: payload });
      setReference(response.reference);
      onSuccess();
    } catch (cause) {
      setError(errorMessage(cause) + (cause instanceof RequestError && Object.keys(cause.fields).length ? ' ' + Object.values(cause.fields).join(' ') : ''));
    } finally { setBusy(false); }
  }
  return <><Modal title={reference ? 'Tu lugar está reservado' : 'Inscríbete al evento'} onClose={() => { if (!busy) onClose(); }}><div className="modal-body">{reference ? <div className="registration-success"><CheckCircle2 size={56}/><p className="eyebrow">Nos vemos pronto</p><h3>¡Te esperamos, {identity.name.split(' ')[0]}!</h3><p>Tu inscripción a <strong>{event.title}</strong> quedó guardada.</p><div className="ticket"><span>Tu número de registro</span><strong>{reference}</strong><span>{formatDate(event.date)} · {event.location}</span></div><p className="muted">Guarda este número o toma una captura. No se envía correo automático.</p><button className="button primary" onClick={() => calendarFile(event)}><Download size={17}/>Guardar en mi calendario</button><button className="button secondary" onClick={onClose}>Volver al evento</button></div> : <><div className="form-event"><span className="category-label">{event.category}</span><strong>{event.title}</strong><span className="muted">{formatDate(event.date)}</span></div><div className="form-progress" aria-hidden="true"><div style={{ width: `${((step + 1) / total) * 100}%` }}/></div><p className="step-label">Paso {step + 1} de {total} · {step === 0 ? 'Tus datos' : isConsent ? 'Confirmación' : 'Sobre tu participación'}</p><form onSubmit={next}>{step === 0 ? <div className="form-fields"><h3>Vamos a conocernos</h3><p className="muted">El formulario debe completarlo una persona mayor de 18 años. Los campos con * son obligatorios.</p><label className="field">Nombre completo del participante *<input autoComplete="name" required maxLength={160} value={identity.name} onChange={e => setIdentity({ ...identity, name: e.target.value })}/></label><div className="field-row"><label className="field">Correo de contacto *<input type="email" autoComplete="email" required maxLength={254} value={identity.email} onChange={e => setIdentity({ ...identity, email: e.target.value })}/></label><label className="field">Teléfono (opcional)<input type="tel" autoComplete="tel" maxLength={40} value={identity.phone} onChange={e => setIdentity({ ...identity, phone: e.target.value })}/></label></div><label className="check-label"><input type="checkbox" checked={identity.is_minor} onChange={e => { setIdentity({ ...identity, is_minor: e.target.checked }); setConsents({ ...consents, guardian_consent: false }); }}/><span>El participante es menor de 18 años</span></label>{identity.is_minor && <fieldset className="guardian-fields"><legend>Datos del representante legal</legend><p className="muted">Solo su representante legal puede inscribir al menor. Usa un correo de contacto adulto, no es necesario el correo del menor.</p><label className="field">Nombre del representante *<input required maxLength={160} value={identity.guardian_name} onChange={e => setIdentity({ ...identity, guardian_name: e.target.value })}/></label><label className="field">Correo del representante *<input required type="email" maxLength={254} value={identity.guardian_email} onChange={e => setIdentity({ ...identity, guardian_email: e.target.value })}/></label></fieldset>}</div> : question ? <div className="form-fields" key={question.id}><h3>{question.label}{question.required && <span aria-label="obligatorio"> *</span>}</h3><QuestionInput question={question} value={answers[question.id] || ''} file={files[question.id]} onChange={value => updateAnswer(question.id, value)} onFile={file => { setFiles(current => { const nextFiles = { ...current }; if (file) nextFiles[question.id] = file; else delete nextFiles[question.id]; return nextFiles; }); setError(''); }}/>{!question.required && <p className="muted small">Esta pregunta es opcional.</p>}</div> : <div className="form-fields"><h3>Antes de reservar tu lugar</h3><div className="privacy-notice"><ShieldCheck size={23}/><p><strong>{settings.organization}</strong> usará tus datos para gestionar esta inscripción y comunicarse contigo sobre el evento. Conservación: {settings.retention_days} días después del evento. Puedes consultar, corregir o solicitar la supresión de tus datos en <a href={`mailto:${settings.contact_email}`}>{settings.contact_email}</a>.</p></div><button type="button" className="text-button" onClick={() => setShowPrivacy(true)}>Leer la política de tratamiento de datos</button><label className="check-label"><input required type="checkbox" checked={consents.adult_confirmed} onChange={e => setConsents({ ...consents, adult_confirmed: e.target.checked })}/><span>Confirmo que soy mayor de 18 años y estoy completando este registro.</span></label><label className="check-label"><input required type="checkbox" checked={consents.consent} onChange={e => setConsents({ ...consents, consent: e.target.checked })}/><span>He leído la política y autorizo el tratamiento de mis datos para gestionar la inscripción.</span></label><label className="check-label"><input required type="checkbox" checked={consents.sensitive_consent} onChange={e => setConsents({ ...consents, sensitive_consent: e.target.checked })}/><span>Autorizo expresamente registrar mi participación en este evento religioso. Entiendo que puede revelar información sensible y que no estoy obligado a facilitarla. Si prefiero no hacerlo en línea, puedo consultar una alternativa con la iglesia en el correo indicado.</span></label>{identity.is_minor && <label className="check-label"><input required type="checkbox" checked={consents.guardian_consent} onChange={e => setConsents({ ...consents, guardian_consent: e.target.checked })}/><span>Declaro ser el representante legal, autorizar la participación y el tratamiento de datos del menor, teniendo en cuenta su opinión según su madurez y su interés superior.</span></label>}</div>}{error && <div role="alert" className="error-notice">{error}</div>}<div className="form-actions">{step > 0 && <button type="button" disabled={busy} className="button secondary" onClick={() => { setError(''); setStep(step - 1); }}><ArrowLeft size={16}/>Atrás</button>}<button className="button primary" disabled={busy}>{busy ? 'Guardando inscripción…' : isConsent ? 'Confirmar inscripción' : 'Continuar'}{!busy && <ArrowRight size={17}/>}</button></div></form></>}</div></Modal>{showPrivacy && <Privacy settings={settings} onClose={() => setShowPrivacy(false)}/>}</>;
}

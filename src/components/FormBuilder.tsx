import { useState } from 'react';
import { ArrowDown, ArrowUp, FileText, Plus, RotateCcw, Trash2 } from 'lucide-react';
import type { Question } from '../../shared/contracts';
import { activeQuestions, pruneAnswers, validateQuestion } from '../flow';
import { ErrorNotice, Modal } from '../ui';
import { fieldTypes, formTemplates, MAX_FILE_QUESTIONS, MAX_QUESTIONS, newQuestion, normalizeQuestions } from '../formTemplates';

interface BuilderProps { questions: Question[]; onChange: (questions: Question[]) => void }

function OptionsEditor({ question, onChange }: { question: Question; onChange: (options: string[]) => void }) {
  const [text, setText] = useState(question.options.join('\n'));
  return <label className="field">Opciones, una por línea<textarea required rows={4} value={text} onChange={event => { setText(event.target.value); onChange(event.target.value.split('\n')); }} onBlur={() => setText(question.options.join('\n'))}/><span className="admin-hint">De 2 a 20 opciones de máximo 200 caracteres. Las opciones vacías y duplicadas se omiten.</span></label>;
}

export default function FormBuilder({ questions, onChange }: BuilderProps) {
  const [confirm, setConfirm] = useState<{ title: string; message: string; action: () => void } | null>(null);
  const files = questions.filter(question => question.type === 'file').length;
  const update = (id: string, patch: Partial<Question>) => onChange(normalizeQuestions(questions.map(question => question.id === id ? { ...question, ...patch } : question)));
  const move = (index: number, offset: number) => {
    const next = [...questions];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    onChange(normalizeQuestions(next));
  };
  return <div className="admin-builder">
    <section className="admin-note"><FileText size={22} aria-hidden="true"/><div><strong>Los datos básicos ya están incluidos</strong><p>Nombre, correo, teléfono, confirmación de mayoría de edad o datos y autorización del acudiente, y autorizaciones de tratamiento. No necesitas crearlos como preguntas.</p></div></section>
    <div className="admin-section-heading"><div><h3>Empieza con una plantilla</h3><p>Las plantillas solo cambian las preguntas personalizadas.</p></div></div>
    <div className="admin-templates">{formTemplates.map(template => <button key={template.id} type="button" className="admin-template" onClick={() => {
      const apply = () => onChange(template.create());
      if (questions.length) setConfirm({ title: '¿Reemplazar las preguntas?', message: `Se reemplazarán las preguntas de este borrador por la plantilla ${template.name}. Las inscripciones ya recibidas conservarán sus respuestas originales.`, action: apply });
      else apply();
    }}><strong>{template.name}</strong><span>{template.description}</span></button>)}</div>
    <div className="admin-section-heading"><div><h3>Preguntas personalizadas</h3><p>{questions.length} de {MAX_QUESTIONS} preguntas · {files} de {MAX_FILE_QUESTIONS} preguntas de archivo</p></div><button type="button" className="button secondary" disabled={questions.length >= MAX_QUESTIONS} onClick={() => onChange([...questions, newQuestion()])}><Plus size={17}/>Agregar pregunta</button></div>
    {!questions.length && <div className="admin-empty"><h3>Un formulario sencillo también funciona</h3><p>Sin preguntas adicionales, solo se solicitarán los datos básicos y las autorizaciones.</p></div>}
    {questions.map((question, index) => <section className="admin-question" key={question.id} aria-label={`Pregunta ${index + 1}`}>
      <div className="admin-question-head"><span className="admin-eyebrow">Pregunta {String(index + 1).padStart(2, '0')}</span><div className="admin-actions"><button type="button" className="admin-icon" disabled={index === 0} aria-label={`Subir pregunta ${index + 1}`} onClick={() => move(index, -1)}><ArrowUp size={18}/></button><button type="button" className="admin-icon" disabled={index === questions.length - 1} aria-label={`Bajar pregunta ${index + 1}`} onClick={() => move(index, 1)}><ArrowDown size={18}/></button><button type="button" className="admin-icon admin-danger" aria-label={`Eliminar pregunta ${index + 1}`} onClick={() => setConfirm({ title: '¿Eliminar esta pregunta del formulario?', message: 'Se quitará del formulario y se limpiarán los saltos que la referencian. Las respuestas recibidas no se borrarán.', action: () => onChange(normalizeQuestions(questions.filter(item => item.id !== question.id))) })}><Trash2 size={18}/></button></div></div>
      <div className="admin-grid-two"><label className="field">Título de la pregunta<input required maxLength={250} value={question.label} onChange={event => update(question.id, { label: event.target.value })} placeholder="¿Qué necesitas saber?"/></label><label className="field">Tipo de respuesta<select value={question.type} onChange={event => update(question.id, { type: event.target.value as Question['type'] })}>{fieldTypes.map(type => <option key={type.value} value={type.value} disabled={type.value === 'file' && question.type !== 'file' && files >= MAX_FILE_QUESTIONS}>{type.label}</option>)}</select></label></div>
      <label className="field">Texto de ayuda <span className="admin-optional">(opcional)</span><input maxLength={500} value={question.help} onChange={event => update(question.id, { help: event.target.value })} placeholder="Añade una indicación breve"/></label>
      <label className="admin-check"><input type="checkbox" checked={question.required} onChange={event => update(question.id, { required: event.target.checked })}/>Respuesta obligatoria</label>
      {question.type === 'file' && <label className="field">Formatos permitidos<select value={question.accept} onChange={event => update(question.id, { accept: event.target.value as Question['accept'] })}><option value="images">Imágenes: JPG, PNG y WEBP</option><option value="documents">Documentos: PDF</option><option value="both">Imágenes y PDF</option></select><span className="admin-hint">Un archivo por pregunta, máximo 5 MB. Acceso privado para personal autorizado.</span></label>}
      {(question.type === 'select' || question.type === 'radio') && <div className="admin-grid-two"><OptionsEditor question={question} onChange={options => update(question.id, { options })}/><div className="admin-rules"><h4>Después de cada respuesta</h4><p className="admin-hint">Solo se permiten saltos hacia preguntas posteriores. Revisa el flujo al reordenar.</p>{question.options.map(option => <label className="field" key={option}><span>{option}</span><select value={question.rules.find(rule => rule.value === option)?.target ?? ''} onChange={event => update(question.id, { rules: [...question.rules.filter(rule => rule.value !== option), ...(event.target.value ? [{ value: option, target: event.target.value }] : [])] })}><option value="">Continuar con la siguiente</option>{questions.slice(index + 1).map((target, targetIndex) => <option key={target.id} value={target.id}>{index + targetIndex + 2}. {target.label || 'Sin título'}</option>)}<option value="__submit__">Ir al final del formulario</option></select></label>)}</div></div>}
    </section>)}
    {questions.length > 0 && <p className="admin-hint">Al cambiar tipos, opciones u orden, se eliminan automáticamente las reglas que ya no son válidas. Ningún cambio elimina inscripciones.</p>}
    {confirm && <Modal title={confirm.title} onClose={() => setConfirm(null)}><div className="admin-confirm"><p>{confirm.message}</p><div className="admin-actions"><button type="button" className="button secondary" onClick={() => setConfirm(null)}>Cancelar</button><button type="button" className="button primary" onClick={() => { confirm.action(); setConfirm(null); }}>Confirmar cambio</button></div></div></Modal>}
  </div>;
}

export function FormPreview({ questions }: { questions: Question[] }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [minor, setMinor] = useState(false);
  const [complete, setComplete] = useState(false);
  const [reset, setReset] = useState(0);
  const visible = activeQuestions(questions, answers);
  const change = (id: string, value: string) => { setComplete(false); setAnswers(previous => pruneAnswers(questions, { ...previous, [id]: value })); };
  return <section className="admin-preview">
    <div className="admin-section-heading"><div><h3>Prueba el formulario</h3><p>Vista previa interactiva. No envía ni guarda datos.</p></div><button type="button" className="button secondary" onClick={() => { setAnswers({}); setMinor(false); setComplete(false); setReset(value => value + 1); }}><RotateCcw size={16}/>Reiniciar</button></div>
    <form key={reset} onSubmit={event => { event.preventDefault(); setComplete(true); }}>
      <fieldset className="admin-fieldset"><legend>Datos básicos integrados</legend><div className="admin-grid-two"><label className="field">Nombre completo<input required autoComplete="off"/></label><label className="field">Correo electrónico<input type="email" required autoComplete="off"/></label><label className="field">Teléfono<input type="tel" required autoComplete="off"/></label></div><label className="admin-check"><input type="checkbox" checked={minor} onChange={event => setMinor(event.target.checked)}/>Soy menor de 18 años</label>{minor ? <div className="admin-grid-two"><label className="field">Nombre del acudiente<input required/></label><label className="field">Correo del acudiente<input type="email" required/></label><label className="admin-check"><input type="checkbox" required/>Autorización del acudiente (simulación)</label></div> : <label className="admin-check"><input type="checkbox" required/>Confirmo que soy mayor de edad (simulación)</label>}</fieldset>
      <fieldset className="admin-fieldset"><legend>Preguntas del evento</legend>{visible.length === 0 && <p>No hay preguntas adicionales.</p>}{visible.map(question => <div className="admin-preview-question" key={question.id}>{question.type === 'radio' ? <fieldset className="admin-radio"><legend>{question.label || 'Pregunta sin título'}{question.required && ' *'}</legend>{question.help && <p className="admin-hint">{question.help}</p>}{question.options.map(option => <label className="admin-check" key={option}><input type="radio" name={`preview-${question.id}`} required={question.required} value={option} checked={answers[question.id] === option} onChange={() => change(question.id, option)}/>{option}</label>)}</fieldset> : <label className="field">{question.label || 'Pregunta sin título'}{question.required && ' *'}{question.type === 'textarea' ? <textarea required={question.required} value={answers[question.id] ?? ''} onChange={event => change(question.id, event.target.value)} rows={3}/> : question.type === 'select' ? <select required={question.required} value={answers[question.id] ?? ''} onChange={event => change(question.id, event.target.value)}><option value="">Selecciona una opción</option>{question.options.map(option => <option key={option}>{option}</option>)}</select> : question.type === 'file' ? <input type="file" required={question.required} accept={question.accept === 'images' ? '.jpg,.jpeg,.png,.webp' : question.accept === 'documents' ? '.pdf' : '.jpg,.jpeg,.png,.webp,.pdf'} onChange={event => { const file = event.target.files?.[0]; event.target.setCustomValidity(validateQuestion(question, '', file)); }}/> : <input type={question.type} required={question.required} value={answers[question.id] ?? ''} onChange={event => change(question.id, event.target.value)}/ >}{question.help && <span className="admin-hint">{question.help}</span>}</label>}</div>)}</fieldset>
      <div className="admin-note"><div><strong>Autorizaciones y política de privacidad</strong><p>La vista pública utiliza la política y versión configuradas. Esta simulación no constituye una autorización legal ni genera una inscripción.</p><label className="admin-check"><input type="checkbox" required/>Simular autorización de tratamiento de datos</label><label className="admin-check"><input type="checkbox" required/>Simular autorización explícita de datos sensibles, cuando corresponda</label></div></div>
      {questions.some(question => ['radio', 'select'].includes(question.type) && !question.options.length) && <ErrorNotice message="Hay preguntas de selección sin opciones. Completa el formulario antes de publicarlo."/>}
      <p className="admin-hint">Se muestran {visible.length} de {questions.length} preguntas personalizadas según tus respuestas.</p><button className="button primary" type="submit">Probar validación · sin enviar</button>{complete && <p className="admin-success" role="status">Prueba completada. No se ha enviado ni guardado ningún dato.</p>}
    </form>
  </section>;
}

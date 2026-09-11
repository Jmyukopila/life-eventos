import type { FieldType, Question } from '../shared/contracts';

export const MAX_QUESTIONS = 40;
export const MAX_FILE_QUESTIONS = 3;
export const fieldTypes: { value: FieldType; label: string }[] = [
  { value: 'text', label: 'Texto corto' },
  { value: 'email', label: 'Correo electrónico' },
  { value: 'tel', label: 'Teléfono' },
  { value: 'textarea', label: 'Texto largo' },
  { value: 'select', label: 'Lista desplegable' },
  { value: 'radio', label: 'Selección única' },
  { value: 'date', label: 'Fecha' },
  { value: 'file', label: 'Archivo adjunto' },
];

export function newQuestion(type: FieldType = 'text', label = ''): Question {
  return { id: `q_${crypto.randomUUID().replaceAll('-', '')}`, label, type, required: false, help: '', options: [], rules: [], accept: 'both' };
}

export function normalizeQuestions(questions: Question[]): Question[] {
  return questions.map((question, index) => {
    const choice = question.type === 'select' || question.type === 'radio';
    const options = choice ? [...new Set(question.options.map(option => option.trim()).filter(Boolean))] : [];
    const later = new Set(questions.slice(index + 1).map(item => item.id));
    const seen = new Set<string>();
    const rules = choice ? question.rules.filter(rule => {
      if (!options.includes(rule.value) || seen.has(rule.value) || (rule.target !== '__submit__' && !later.has(rule.target))) return false;
      seen.add(rule.value);
      return true;
    }) : [];
    return { ...question, options, rules };
  });
}

function choice(label: string, options: string[], required = false): Question {
  return { ...newQuestion('radio', label), options, required };
}

export const formTemplates = [
  { id: 'church', name: 'Iglesia', description: 'Primera visita y acompañantes.', create: (): Question[] => [choice('¿Es tu primera visita?', ['Sí', 'No']), newQuestion('text', '¿Cuántas personas te acompañan?'), newQuestion('textarea', '¿Qué información adicional necesitas para asistir?')] },
  { id: 'connection', name: 'Grupos de conexión', description: 'Zona, disponibilidad y modalidad.', create: (): Question[] => [newQuestion('text', '¿En qué barrio o zona vives?'), choice('¿Qué modalidad prefieres?', ['Presencial', 'Virtual', 'Cualquiera']), { ...newQuestion('select', '¿Qué día tienes disponibilidad?'), options: ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'] }] },
  { id: 'families', name: 'Familias', description: 'Participantes y actividades para compartir.', create: (): Question[] => [newQuestion('text', '¿Cuántas personas de tu familia asistirán?'), choice('¿Asistirán niños o niñas contigo?', ['Sí', 'No']), newQuestion('textarea', '¿Qué actividades les gustaría compartir?')] },
  { id: 'youth', name: 'Jóvenes', description: 'Intereses y participación en actividades.', create: (): Question[] => [choice('¿Has participado antes en nuestros encuentros?', ['Sí', 'No']), { ...newQuestion('select', '¿Qué actividad te interesa más?'), options: ['Música', 'Deporte', 'Conversación', 'Servicio'] }, newQuestion('textarea', '¿Qué te gustaría encontrar en este encuentro?')] },
];

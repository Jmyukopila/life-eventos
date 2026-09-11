import type { Question } from '../shared/contracts';

export function activeQuestions(questions: Question[], answers: Record<string, string>): Question[] {
  const result: Question[] = [];
  for (let index = 0; index < questions.length;) {
    const question = questions[index];
    result.push(question);
    const rule = question.rules.find(item => item.value === answers[question.id]);
    if (rule?.target === '__submit__') break;
    const target = rule ? questions.findIndex(item => item.id === rule.target) : -1;
    index = target > index ? target : index + 1;
  }
  return result;
}
export function pruneAnswers(questions: Question[], answers: Record<string, string>): Record<string, string> {
  const visible = new Set(activeQuestions(questions, answers).map(question => question.id));
  return Object.fromEntries(Object.entries(answers).filter(([id]) => visible.has(id)));
}
export function validateQuestion(question: Question, value: string, file?: File): string {
  if (question.type === 'file') {
    if (!file) return question.required ? 'Selecciona un archivo.' : '';
    if (file.size > 5 * 1024 * 1024) return 'El archivo debe pesar como máximo 5 MB.';
    const extensions = question.accept === 'images' ? /\.(jpe?g|png|webp)$/i : question.accept === 'documents' ? /\.pdf$/i : /\.(jpe?g|png|webp|pdf)$/i;
    if (!extensions.test(file.name)) return 'Formato no permitido. Usa los formatos indicados.';
    return '';
  }
  if (!value.trim()) return question.required ? 'Responde esta pregunta para continuar.' : '';
  if (value.length > 4000) return 'Usa como máximo 4000 caracteres.';
  if (question.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Escribe un correo válido.';
  if (['select', 'radio'].includes(question.type) && !question.options.includes(value)) return 'Selecciona una de las opciones.';
  return '';
}

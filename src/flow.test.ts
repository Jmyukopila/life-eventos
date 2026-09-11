import { describe, expect, it } from 'vitest';
import { activeQuestions, pruneAnswers, validateQuestion } from './flow';
import type { Question } from '../shared/contracts';

const questions: Question[] = [
  { id: 'member', label: '¿Tienes grupo?', type: 'radio', required: true, help: '', options: ['Sí', 'No'], rules: [{ value: 'No', target: 'availability' }], accept: 'both' },
  { id: 'leader', label: 'Líder', type: 'text', required: true, help: '', options: [], rules: [], accept: 'both' },
  { id: 'availability', label: 'Disponibilidad', type: 'text', required: true, help: '', options: [], rules: [], accept: 'both' },
];
describe('recorrido del formulario', () => {
  it('salta una pregunta requerida si responde No', () => {
    expect(activeQuestions(questions, { member: 'No' }).map(q => q.id)).toEqual(['member', 'availability']);
  });
  it('conserva la secuencia si responde Sí', () => {
    expect(activeQuestions(questions, { member: 'Sí' }).map(q => q.id)).toEqual(['member', 'leader', 'availability']);
  });
  it('descarta respuestas de un camino abandonado', () => {
    expect(pruneAnswers(questions, { member: 'No', leader: 'Dato anterior', availability: 'Sábado', unknown: 'x' })).toEqual({ member: 'No', availability: 'Sábado' });
  });
  it('termina antes cuando la regla envía al final', () => {
    const form = [{ ...questions[0], rules: [{ value: 'No', target: '__submit__' }] }, questions[1]];
    expect(activeQuestions(form, { member: 'No' }).map(q => q.id)).toEqual(['member']);
  });
  it('no entra en ciclos incluso con una regla inválida', () => {
    expect(activeQuestions([{ ...questions[0], rules: [{ value: 'No', target: 'member' }] }], { member: 'No' })).toHaveLength(1);
  });
  it('valida requeridos, opciones y correos', () => {
    expect(validateQuestion(questions[0], '')).not.toBe('');
    expect(validateQuestion(questions[0], 'Tal vez')).not.toBe('');
    expect(validateQuestion(questions[0], 'Sí')).toBe('');
    expect(validateQuestion({ ...questions[1], type: 'email' }, 'sin-arroba')).not.toBe('');
  });
});

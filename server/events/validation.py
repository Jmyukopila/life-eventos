import re
from datetime import date
from io import BytesIO
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .security import ApiProblem

CATEGORIES = ['Iglesia', 'Grupos de conexión', 'Jóvenes', 'Familias', 'Servicio']
TYPES = ['text', 'email', 'tel', 'textarea', 'select', 'radio', 'date', 'file']
POSTERS = {'encuentro', 'conexion', 'jovenes', 'familias', 'servicio', 'adoracion'}


def text(data, key, maximum, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ApiProblem(f'Revisa el campo {key}.', fields={key: f'Escribe entre {1 if required else 0} y {maximum} caracteres.'})
    return value.strip()


def email(data, key, required=True):
    value = text(data, key, 254, required).lower()
    if value:
        try:
            validate_email(value)
        except ValidationError:
            raise ApiProblem('Escribe un correo válido.', fields={key: 'Correo no válido.'})
    return value


def boolean(data, key, default=False):
    value = data.get(key, default)
    if type(value) is not bool:
        raise ApiProblem(f'El campo {key} debe ser verdadero o falso.')
    return value


def integer(data, key, minimum, maximum):
    value = data.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ApiProblem(f'{key} debe estar entre {minimum} y {maximum}.', fields={key: 'Número fuera del rango permitido.'})
    return value


def image_url(value):
    if not isinstance(value, str):
        raise ApiProblem('Selecciona una imagen válida.')
    if value in {f'/posters/{name}.svg' for name in POSTERS}:
        return value
    if re.fullmatch(r'/media/[a-f0-9]{32}\.jpg', value):
        # Mirar el disco aquí rompía el panel entero con Supabase activo: la portada recién
        # subida vive en el bucket, no en MEDIA_ROOT, y el evento se rechazaba al guardar.
        from . import storage
        if storage.exists(value.rsplit('/', 1)[-1], False):
            return value
    raise ApiProblem('Sube una imagen o selecciona una portada de ejemplo.')


def questions_schema(value):
    if not isinstance(value, list) or len(value) > 40:
        raise ApiProblem('El formulario admite hasta 40 preguntas.')
    ids = []
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ApiProblem('Pregunta no válida.')
        qid = text(item, 'id', 80)
        if not re.fullmatch(r'[A-Za-z0-9_-]+', qid) or qid in ids:
            raise ApiProblem('Las preguntas deben tener identificadores únicos.')
        ids.append(qid)
        kind = item.get('type')
        if kind not in TYPES:
            raise ApiProblem('Tipo de pregunta no válido.')
        options = item.get('options', [])
        if not isinstance(options, list) or len(options) > 20 or any(not isinstance(opt, str) or not opt.strip() or len(opt) > 200 for opt in options):
            raise ApiProblem('Usa hasta 20 opciones no vacías por pregunta.')
        if len(set(options)) != len(options) or (kind in ['select', 'radio'] and len(options) < 2):
            raise ApiProblem('Usa al menos dos opciones diferentes.')
        rules = item.get('rules', [])
        if not isinstance(rules, list) or len(rules) > len(options) or (rules and kind not in ['select', 'radio']):
            raise ApiProblem('Solo las preguntas de selección pueden tener saltos.')
        accept = item.get('accept', 'both')
        if accept not in ['images', 'documents', 'both']:
            raise ApiProblem('Formato de archivo no válido.')
        cleaned.append({'id': qid, 'label': text(item, 'label', 250), 'type': kind, 'required': boolean(item, 'required'), 'help': text(item, 'help', 500, False), 'options': options, 'rules': rules, 'accept': accept})
    if sum(q['type'] == 'file' for q in cleaned) > 3:
        raise ApiProblem('Usa como máximo tres preguntas de archivo.')
    for index, question in enumerate(cleaned):
        values = []
        for rule in question['rules']:
            if not isinstance(rule, dict) or rule.get('value') not in question['options'] or rule.get('value') in values:
                raise ApiProblem('Cada opción puede tener un solo salto.')
            if rule.get('target') != '__submit__' and rule.get('target') not in ids[index + 1:]:
                raise ApiProblem('Los saltos solo pueden ir a una pregunta posterior o al final.')
            values.append(rule['value'])
    return cleaned


def event_input(data):
    result = {key: text(data, key, maximum) for key, maximum in [('title', 160), ('summary', 280), ('description', 20000), ('location', 300)]}
    if data.get('category') not in CATEGORIES or data.get('status') not in ['draft', 'published', 'closed']:
        raise ApiProblem('Categoría o estado no válido.')
    for key in ['date', 'end_date']:
        raw = data.get(key)
        parsed = parse_datetime(raw) if isinstance(raw, str) else None
        if key == 'end_date' and raw is None:
            result[key] = None
        elif not parsed or timezone.is_naive(parsed):
            raise ApiProblem('La fecha debe incluir zona horaria.', fields={key: 'Fecha no válida.'})
        else:
            result[key] = parsed
    if result['end_date'] and result['end_date'] <= result['date']:
        raise ApiProblem('La fecha de cierre debe ser posterior al inicio.')
    gallery = data.get('gallery', [])
    if not isinstance(gallery, list) or len(gallery) > 8:
        raise ApiProblem('La galería admite hasta ocho imágenes.')
    result.update(category=data['category'], status=data['status'], capacity=integer(data, 'capacity', 1, 100000), featured=boolean(data, 'featured'), cover=image_url(data.get('cover')), gallery=[image_url(url) for url in gallery], questions=questions_schema(data.get('questions', [])))
    return result


def active_questions(questions, answers):
    result, index = [], 0
    while index < len(questions):
        question = questions[index]
        result.append(question)
        rule = next((r for r in question['rules'] if r['value'] == answers.get(question['id'])), None)
        if rule and rule['target'] == '__submit__':
            break
        target = next((i for i, q in enumerate(questions) if q['id'] == rule['target']), -1) if rule else -1
        index = target if target > index else index + 1
    return result


def validate_answers(questions, answers, files):
    if not isinstance(answers, dict) or len(answers) > 40 or any(not isinstance(v, str) or len(v) > 4000 for v in answers.values()):
        raise ApiProblem('Respuestas no válidas.')
    active = active_questions(questions, answers)
    allowed = {q['id'] for q in active if q['type'] != 'file'}
    file_keys = {f"file_{q['id']}" for q in active if q['type'] == 'file'}
    if set(answers) - allowed or set(files) - file_keys:
        raise ApiProblem('El formulario contiene respuestas fuera del recorrido activo.')
    validated_files = []
    for question in active:
        key = question['id']
        value = answers.get(key, '').strip()
        if question['type'] == 'file':
            uploaded = files.getlist(f'file_{key}')
            if len(uploaded) > 1 or (question['required'] and not uploaded):
                raise ApiProblem('Selecciona un archivo por pregunta.', fields={key: 'Archivo requerido o duplicado.'})
            if uploaded:
                validated_files.append((key, uploaded[0], inspect_file(uploaded[0], question['accept'])))
            continue
        if not value:
            if question['required']:
                raise ApiProblem('Completa las preguntas obligatorias.', fields={key: 'Esta respuesta es obligatoria.'})
            continue
        if question['type'] in ['select', 'radio'] and value not in question['options']:
            raise ApiProblem('Selecciona una opción válida.', fields={key: 'Opción no válida.'})
        if question['type'] == 'email':
            email({key: value}, key)
        if question['type'] == 'date':
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ApiProblem('Escribe una fecha válida.', fields={key: 'Fecha no válida.'})
    return active, validated_files


def inspect_file(upload, accept='both', public=False):
    if upload.size > 5 * 1024 * 1024 or upload.size == 0:
        raise ApiProblem('Cada archivo debe pesar entre 1 byte y 5 MB.')
    raw = upload.read()
    upload.seek(0)
    extension = Path(upload.name).suffix.lower()
    if not public and accept in ['both', 'documents'] and extension == '.pdf' and raw.startswith(b'%PDF-') and b'%%EOF' in raw[-2048:]:
        return raw, 'application/pdf', '.pdf'
    if accept == 'documents' or extension not in ['.jpg', '.jpeg', '.png', '.webp']:
        raise ApiProblem('Usa JPG, PNG, WebP o PDF según lo indicado.')
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ['JPEG', 'PNG', 'WEBP'] or image.width * image.height > 10000000:
                raise ApiProblem('La imagen debe tener como máximo 10 megapíxeles.')
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image.thumbnail((2400, 2400))
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=88)
            return output.getvalue(), 'image/jpeg', '.jpg'
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ApiProblem('El archivo no es una imagen válida.')

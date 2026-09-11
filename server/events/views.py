import csv
import secrets
import hashlib
import json
import time
import uuid
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import F
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token, rotate_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from . import storage
from . import retention
from .models import Attachment, Event, Registration, SiteSettings
from .scope import RANGO_ROL
from .security import ApiProblem, body_json, endpoint, failure
from .validation import boolean, email, event_input, inspect_file, integer, text, validate_answers


def site_settings():
    return SiteSettings.objects.get_or_create(pk=1)[0]


def settings_data(site):
    return {**{field: getattr(site, field) for field in ['organization', 'contact_email', 'contact_phone', 'address', 'privacy_policy', 'privacy_version', 'retention_days', 'registration_enabled']}, 'ready': site.ready}


def event_data(event):
    return {**{key: getattr(event, key) for key in ['title', 'category', 'summary', 'description', 'location', 'capacity', 'registered', 'cover', 'gallery', 'status', 'featured', 'questions', 'form_version']}, 'id': str(event.id), 'date': event.date.isoformat(), 'end_date': event.end_date.isoformat() if event.end_date else None, 'created_at': event.created_at.isoformat()}


def get_event(event_id, public=False, scope=None, write=False):
    if scope is not None:
        query = scope.owned_events() if write else scope.events()
    else:
        query = Event.objects.all()
    if public:
        query = query.exclude(status='draft')
    event = query.filter(pk=event_id).first()
    if not event:
        # Mismo mensaje tanto si el evento no existe como si existe fuera del ámbito:
        # no se confirma ni la existencia del recurso.
        raise ApiProblem('No encontramos este evento.', 'not_found', 404)
    return event


def session_data(request):
    authorized = request.user.is_authenticated and request.user.is_staff and request.user.is_active
    if authorized and time.time() - request.session.get('authenticated_at', 0) > 43200:
        logout(request)
        authorized = False
    return {'authenticated': bool(authorized), 'username': request.user.username if authorized else '', 'csrfToken': get_token(request)}


@ensure_csrf_cookie
@endpoint(['GET'])
def session_view(request):
    return JsonResponse(session_data(request))


@endpoint(['POST'])
def login_view(request):
    data = body_json(request)
    username = text(data, 'username', 150)
    password = text(data, 'password', 1024)
    user = authenticate(request, username=username, password=data['password'])
    if not user or not user.is_active or not user.is_staff:
        return failure('Credenciales inválidas.', 'invalid_credentials', 401)
    login(request, user)
    request.session['authenticated_at'] = time.time()
    return JsonResponse(session_data(request))


@endpoint(['POST'])
def logout_view(request):
    logout(request)
    rotate_token(request)
    return JsonResponse({'ok': True})


@csrf_exempt
@endpoint(['POST'])
def purga_programada(request):
    # Lo dispara un cron externo, no un navegador: se autentica con token, no con cookie, y por
    # eso queda fuera de CSRF. Sin token configurado el endpoint no existe; anunciar una
    # superficie destructiva que nadie puede usar no aporta nada.
    esperado = settings.TAREAS_TOKEN
    if not esperado:
        raise ApiProblem('No encontrado.', 'not_found', 404)
    if len(esperado) < 32:
        raise ApiProblem('El token de tareas es demasiado corto para proteger esto.', 'misconfigured', 503)
    entregado = request.headers.get('Authorization', '')
    prefijo = 'Bearer '
    if not entregado.startswith(prefijo) or not secrets.compare_digest(
            entregado[len(prefijo):].encode(), esperado.encode()):
        raise ApiProblem('No autorizado.', 'unauthorized', 401)
    purgados, fallos = retention.purgar()
    if fallos:
        # 500 a propósito: el cron tiene que poder avisar de que hay datos personales fuera de
        # plazo que no se pudieron borrar.
        return JsonResponse({'purgados': purgados, 'fallidos': [ref for ref, _ in fallos]}, status=500)
    return JsonResponse({'purgados': purgados, 'fallidos': []})


@endpoint(['GET'])
def healthz(request):
    # Comprueba que hay base de datos: sin ella este servicio no puede responder nada útil,
    # así que marcarlo como sano sería mentir. Un fallo aquí sale como 500.
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'ok': True})


@endpoint(['GET'])
def public_settings(request):
    return JsonResponse(settings_data(site_settings()))


@endpoint(['PUT'], staff=True, permission='settings.edit')
def admin_settings(request):
    data = body_json(request)
    site = site_settings()
    values = {
        'organization': text(data, 'organization', 200),
        'contact_email': email(data, 'contact_email', False),
        'contact_phone': text(data, 'contact_phone', 40, False),
        'address': text(data, 'address', 500, False),
        'privacy_policy': text(data, 'privacy_policy', 50000, False),
        'privacy_version': text(data, 'privacy_version', 80),
        'retention_days': integer(data, 'retention_days', 1, 730),
        'registration_enabled': boolean(data, 'registration_enabled'),
    }
    if site.privacy_policy and values['privacy_policy'] != site.privacy_policy and values['privacy_version'] == site.privacy_version:
        raise ApiProblem('Cambia la versión al modificar la política de tratamiento.')
    for key, value in values.items():
        setattr(site, key, value)
    if site.registration_enabled and not site.ready:
        raise ApiProblem('Completa responsable, correo, dirección y política de tratamiento (mínimo 200 caracteres) antes de habilitar registros.')
    site.save()
    return JsonResponse(settings_data(site))


@endpoint(['GET'])
def public_events(request):
    return JsonResponse({'events': [event_data(event) for event in Event.objects.exclude(status='draft')]})


@endpoint(['GET'])
def public_event(request, event_id):
    return JsonResponse(event_data(get_event(event_id, True)))


@endpoint(['GET', 'POST'], staff=True, permission='event.view')
def admin_events(request):
    if request.method == 'GET':
        return JsonResponse({'events': [event_data(event) for event in request.scope.events()]})
    if not request.scope.can('event.create'):
        raise ApiProblem('No tienes permiso para crear eventos.', 'forbidden', 403)
    # El dueño es el nodo de la membresía de rango más alto: owner/guests en el cuerpo se
    # ignoran en esta fase (event_input no los extrae) porque fijarlos es fase 4 (event.assign).
    owner = min(request.scope.memberships, key=lambda m: RANGO_ROL.index(m.role)).node
    event = Event.objects.create(**event_input(body_json(request)), owner=owner)
    return JsonResponse(event_data(event), status=201)


@endpoint(['PUT'], staff=True, permission='event.edit')
def admin_event(request, event_id):
    values = event_input(body_json(request))
    with transaction.atomic():
        event = get_event(event_id, scope=request.scope, write=True)
        publicando = (values['status'] == 'published' and event.status != 'published') or (values['featured'] and not event.featured)
        if publicando and not request.scope.can('event.publish'):
            raise ApiProblem('No puedes publicar eventos.', 'forbidden', 403)
        if values['capacity'] < event.registered:
            raise ApiProblem('El cupo no puede ser menor al número de inscritos.', 'capacity_conflict', 409)
        if values['questions'] != event.questions:
            event.form_version += 1
        for key, value in values.items():
            setattr(event, key, value)
        event.save()
    return JsonResponse(event_data(event))


@endpoint(['POST'], staff=True, permission='event.edit')
def admin_images(request):
    if set(request.FILES) != {'file'} or len(request.FILES.getlist('file')) != 1:
        raise ApiProblem('Selecciona una imagen.')
    raw, content_type, extension = inspect_file(request.FILES['file'], 'images', True)
    name = storage.save(raw, content_type, extension, False)
    return JsonResponse({'url': f'/media/{name}'}, status=201)


@endpoint(['GET'])
def public_image(request, filename):
    import re
    if not re.fullmatch(r'[a-f0-9]{32}\.jpg', filename):
        raise ApiProblem('Imagen no encontrada.', 'not_found', 404)
    url = storage.public_url(filename)
    if url:
        return HttpResponseRedirect(url)
    path = settings.MEDIA_ROOT / filename
    if not path.is_file():
        raise ApiProblem('Imagen no encontrada.', 'not_found', 404)
    response = FileResponse(path.open('rb'), content_type='image/jpeg')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def registration_values(data):
    is_minor = boolean(data, 'is_minor')
    if not all(boolean(data, key) for key in ['consent', 'sensitive_consent', 'adult_confirmed']):
        raise ApiProblem('El registro debe completarlo una persona adulta que autorice el tratamiento de datos.')
    result = {'name': text(data, 'name', 160), 'email': email(data, 'email'), 'phone': text(data, 'phone', 40, False), 'is_minor': is_minor, 'guardian_name': '', 'guardian_email': ''}
    if is_minor:
        if not boolean(data, 'guardian_consent'):
            raise ApiProblem('Se necesita autorización del representante legal para registrar al menor.')
        result.update(guardian_name=text(data, 'guardian_name', 160), guardian_email=email(data, 'guardian_email'))
    return result


@endpoint(['POST'])
def register(request, event_id):
    key = f"registration-rate:{request.META.get('REMOTE_ADDR', '')}"
    attempts = cache.get(key, 0)
    if attempts >= 30:
        raise ApiProblem('Demasiadas solicitudes. Inténtalo en unos minutos.', 'rate_limit', 429)
    cache.set(key, attempts + 1, 300)
    data = json.loads(request.POST.get('data', '{}'))
    if not isinstance(data, dict):
        raise ApiProblem('Registro no válido.')
    values = registration_values(data)
    request_id = uuid.UUID(text(data, 'request_id', 36))
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode())
    for key in sorted(request.FILES):
        for upload in request.FILES.getlist(key):
            if upload.size > 5 * 1024 * 1024:
                raise ApiProblem('Cada archivo debe pesar como máximo 5 MB.')
            fingerprint.update(json.dumps([key, upload.name, upload.size]).encode())
            fingerprint.update(hashlib.sha256(upload.read()).digest())
            upload.seek(0)
    request_fingerprint = fingerprint.hexdigest()
    created_paths = []
    try:
        with transaction.atomic():
            event = get_event(event_id, True)
            existing = Registration.objects.filter(request_id=request_id).first()
            if existing:
                if existing.event_id != event.id or existing.request_fingerprint != request_fingerprint:
                    raise ApiProblem('La referencia de envío ya fue utilizada.', 'duplicate_request', 409)
                return JsonResponse({'reference': existing.reference, 'duplicate': True})
            site = site_settings()
            if not site.ready:
                raise ApiProblem('Las inscripciones todavía no están habilitadas. Consulta con la iglesia.', 'registration_disabled', 503)
            if data.get('form_version') != event.form_version or data.get('privacy_version') != site.privacy_version:
                raise ApiProblem('El formulario o la política cambió. Recarga el evento antes de registrarte.', 'version_conflict', 409)
            if event.status != 'published' or event.date <= timezone.now():
                raise ApiProblem('Las inscripciones para este evento están cerradas.', 'closed', 409)
            if Registration.objects.filter(event=event, email=values['email'], name=values['name']).exists():
                raise ApiProblem('Esta persona ya está inscrita en el evento.', 'already_registered', 409)
            answers = data.get('answers', {})
            active, files = validate_answers(event.questions, answers, request.FILES)
            if not Event.objects.filter(pk=event.id, registered__lt=F('capacity')).update(registered=F('registered') + 1):
                raise ApiProblem('El evento ya no tiene cupos disponibles.', 'full', 409)
            record = Registration.objects.create(event=event, request_id=request_id, request_fingerprint=request_fingerprint, reference=f'LIFE-{uuid.uuid4().hex[:12].upper()}', **values, answers=answers, question_labels={q['id']: q['label'] for q in active}, form_snapshot=event.questions, privacy_version=site.privacy_version, privacy_snapshot=site.privacy_policy, consent_evidence={'consent': True, 'sensitive_consent': True, 'adult_confirmed': True, 'guardian_consent': bool(values['is_minor']), 'organization': site.organization, 'contact_email': site.contact_email, 'address': site.address, 'timestamp': timezone.now().isoformat()}, expires_at=max(event.date, timezone.now()) + timedelta(days=site.retention_days))
            for question_id, upload, (raw, content_type, extension) in files:
                storage_name = storage.save(raw, content_type, extension, True)
                created_paths.append(storage_name)
                Attachment.objects.create(registration=record, question_id=question_id, name=Path(upload.name).name[:255], storage_name=storage_name, content_type=content_type)
        return JsonResponse({'reference': record.reference, 'duplicate': False}, status=201)
    except Exception:
        for storage_name in created_paths:
            # Limpieza oportunista: si tampoco se puede borrar, manda el error original.
            try:
                storage.delete(storage_name, True)
            except Exception:
                pass
        raise


def registration_data(record):
    return {**{key: getattr(record, key) for key in ['reference', 'name', 'email', 'phone', 'is_minor', 'guardian_name', 'guardian_email', 'answers', 'question_labels', 'privacy_version']}, 'id': str(record.id), 'event_id': str(record.event_id), 'event_title': record.event.title, 'created_at': record.created_at.isoformat(), 'attachments': [{'id': str(file.id), 'name': file.name, 'question_id': file.question_id, 'url': f'/api/admin/files/{file.id}'} for file in record.attachments.all()]}


def registrations_query(request):
    query = Registration.objects.filter(event__in=request.scope.events()).select_related('event').prefetch_related('attachments')
    if request.GET.get('event_id'):
        # Resuelto con el mismo scope: un evento ajeno da 404 aquí, no una lista vacía.
        event = get_event(request.GET['event_id'], scope=request.scope)
        query = query.filter(event_id=event.id)
    return query


@endpoint(['GET'], staff=True, permission='registration.view')
def admin_registrations(request):
    return JsonResponse({'registrations': [registration_data(record) for record in registrations_query(request)]})


@endpoint(['GET'], staff=True, permission='registration.view')
def private_file(request, file_id):
    file = Attachment.objects.filter(pk=file_id, registration__event__in=request.scope.events()).first()
    if not file:
        raise ApiProblem('Archivo no encontrado.', 'not_found', 404)
    url = storage.signed_url(file.storage_name)
    if url:
        return HttpResponseRedirect(url)
    handle = storage.open_private(file.storage_name)
    if not handle:
        raise ApiProblem('Archivo no encontrado.', 'not_found', 404)
    response = FileResponse(handle, as_attachment=True, filename=file.name, content_type=file.content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response


@endpoint(['GET'], staff=True, permission='registration.export')
def export_registrations(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inscripciones-life.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Referencia', 'Evento', 'Fecha', 'Nombre', 'Correo', 'Teléfono', 'Menor', 'Representante', 'Correo representante', 'Respuestas'])
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
    for record in registrations_query(request):
        writer.writerow([safe(value) for value in [record.reference, record.event.title, record.created_at.isoformat(), record.name, record.email, record.phone, 'Sí' if record.is_minor else 'No', record.guardian_name, record.guardian_email, json.dumps({record.question_labels.get(key, key): value for key, value in record.answers.items()}, ensure_ascii=False)]])
    return response


def not_found(request, exception=None):
    return failure('La página solicitada no existe.', 'not_found', 404)


def server_error(request):
    return failure('No pudimos completar la solicitud.', 'server_error', 500)


def index(request):
    path = settings.ROOT_DIR / 'dist' / 'index.html'
    if not path.is_file():
        return HttpResponse('Ejecuta npm run dev para desarrollo, o npm run build para servir la aplicación.', status=503)
    return FileResponse(path.open('rb'), content_type='text/html')

import json
import urllib.error
import urllib.request
import uuid
from django.conf import settings
from .security import ApiProblem


def _bucket(private):
    return settings.SUPABASE_BUCKET_PRIVATE if private else settings.SUPABASE_BUCKET_PUBLIC


def _root(private):
    return settings.PRIVATE_ROOT if private else settings.MEDIA_ROOT


def _headers(content_type=None, extra=None):
    headers = {
        'apikey': settings.SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}',
    }
    if content_type:
        headers['Content-Type'] = content_type
    if extra:
        headers.update(extra)
    return headers


def _request(method, url, headers, body=None):
    # Devuelve (status, cuerpo). Un fallo de transporte (DNS, conexión rechazada, timeout)
    # se traduce aquí mismo a ApiProblem; un status de error HTTP se devuelve tal cual para
    # que cada operación decida su propio mensaje.
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise ApiProblem('No pudimos comunicarnos con el almacenamiento. Inténtalo de nuevo.', 'storage_unavailable', 502) from exc


def _ausente(status, cuerpo):
    # Supabase no usa 404 para "el objeto no está": responde 400 y mete el 404 real dentro del
    # cuerpo JSON ({"statusCode":"404","error":"not_found","code":"NoSuchKey"}). Con HEAD ni
    # siquiera manda cuerpo, así que ahí el 400 pelado ya significa ausencia.
    if status == 404:
        return True
    if status != 400:
        return False
    if not cuerpo:
        return True
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        return False
    return datos.get('error') == 'not_found' or datos.get('code') == 'NoSuchKey'


def exists(storage_name, private):
    if not settings.USE_SUPABASE_STORAGE:
        return (_root(private) / storage_name).is_file()
    url = f'{settings.SUPABASE_URL}/storage/v1/object/{_bucket(private)}/{storage_name}'
    # HEAD en vez de GET: la comprobación no necesita descargar la imagen entera.
    status, cuerpo = _request('HEAD', url, _headers())
    if _ausente(status, cuerpo):
        return False
    if status >= 300:
        raise ApiProblem('No pudimos comprobar el archivo en el almacenamiento.', 'storage_error', 502)
    return True


def save(raw, content_type, extension, private):
    name = f'{uuid.uuid4().hex}{extension}'
    if settings.USE_SUPABASE_STORAGE:
        url = f'{settings.SUPABASE_URL}/storage/v1/object/{_bucket(private)}/{name}'
        status, _ = _request('POST', url, _headers(content_type, {'x-upsert': 'true'}), raw)
        if status >= 300:
            raise ApiProblem('No pudimos guardar el archivo. Inténtalo de nuevo.', 'storage_error', 502)
        return name
    root = _root(private)
    root.mkdir(parents=True, exist_ok=True, **({'mode': 0o700} if private else {}))
    path = root / name
    path.write_bytes(raw)
    if private:
        path.chmod(0o600)
    return name


def delete(storage_name, private):
    # Propaga el fallo a propósito: un borrado que no ocurre deja datos personales vivos
    # más allá de su plazo de retención, y quien llama tiene que poder enterarse.
    # Un 404 es éxito: el archivo ya no está, que es justo lo que se pedía.
    if settings.USE_SUPABASE_STORAGE:
        url = f'{settings.SUPABASE_URL}/storage/v1/object/{_bucket(private)}/{storage_name}'
        status, cuerpo = _request('DELETE', url, _headers())
        if status >= 300 and not _ausente(status, cuerpo):
            raise ApiProblem('No pudimos borrar el archivo del almacenamiento.', 'storage_error', 502)
        return
    (_root(private) / storage_name).unlink(missing_ok=True)


def public_url(storage_name):
    if not settings.USE_SUPABASE_STORAGE:
        return None
    return f'{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET_PUBLIC}/{storage_name}'


def signed_url(storage_name):
    if not settings.USE_SUPABASE_STORAGE:
        return None
    url = f'{settings.SUPABASE_URL}/storage/v1/object/sign/{settings.SUPABASE_BUCKET_PRIVATE}/{storage_name}'
    body = json.dumps({'expiresIn': settings.SUPABASE_SIGNED_URL_TTL}).encode()
    status, response_body = _request('POST', url, _headers('application/json'), body)
    if status >= 300:
        raise ApiProblem('No pudimos generar el enlace del archivo. Inténtalo de nuevo.', 'storage_error', 502)
    relative = json.loads(response_body)['signedURL']
    return f'{settings.SUPABASE_URL}/storage/v1{relative}'


def open_private(storage_name):
    path = settings.PRIVATE_ROOT / storage_name
    return path.open('rb') if path.is_file() else None

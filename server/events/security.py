import json
import time
from functools import wraps
from django.core.exceptions import ValidationError, RequestDataTooBig, TooManyFilesSent
from django.http import JsonResponse


class ApiProblem(Exception):
    def __init__(self, message, code='invalid', status=400, fields=None):
        self.message, self.code, self.status, self.fields = message, code, status, fields


def failure(message, code='invalid', status=400, fields=None):
    body = {'code': code, 'message': message}
    if fields:
        body['fields'] = fields
    return JsonResponse({'error': body}, status=status)


def endpoint(methods, staff=False, permission=None):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return failure('Método no permitido.', 'method_not_allowed', 405)
            if staff:
                if not request.user.is_authenticated or not request.user.is_staff or not request.user.is_active:
                    return failure('Inicia sesión como administrador.', 'unauthorized', 401)
                if time.time() - request.session.get('authenticated_at', 0) > 43200:
                    request.session.flush()
                    return failure('La sesión venció. Inicia sesión nuevamente.', 'session_expired', 401)
                from .scope import Scope  # import tardío: evita un ciclo con views/scope
                request.scope = Scope(request.user)
                if permission and not request.scope.can(permission):
                    return failure('No tienes permiso para esta acción.', 'forbidden', 403)
            try:
                response = view(request, *args, **kwargs)
                response['Cache-Control'] = 'no-store'
                response['X-Frame-Options'] = 'DENY'
                return response
            except ApiProblem as exc:
                return failure(exc.message, exc.code, exc.status, exc.fields)
            except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError, TypeError, RequestDataTooBig, TooManyFilesSent):
                return failure('Revisa los datos enviados. La solicitud no es válida.')
        return wrapped
    return decorate


def body_json(request):
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ApiProblem('Se esperaba un objeto de datos.')
    return data


def csrf_failure(request, reason=''):
    return failure('La sesión de seguridad cambió. Recarga la página e inténtalo de nuevo.', 'csrf', 403)


def locked_out(request, credentials=None, *args, **kwargs):
    return failure('Demasiados intentos. Espera 20 minutos antes de volver a intentarlo.', 'locked_out', 429)

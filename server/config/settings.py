import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
TESTING = 'test' in sys.argv
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Configura DJANGO_SECRET_KEY antes de iniciar producción.')
    SECRET_KEY = get_random_secret_key()
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1'] if TESTING else os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'axes', 'events']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'axes.middleware.AxesMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
SQLITE = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('DATABASE_PATH', BASE_DIR / 'db.sqlite3'), 'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}


def postgres(url):
    parts = urlparse(url)
    if parts.scheme not in ['postgres', 'postgresql'] or not parts.hostname or not parts.username:
        raise RuntimeError('DATABASE_URL no es una URI de PostgreSQL válida. Recuerda percent-codificar la contraseña: @ es %40, & es %26, : es %3A, / es %2F.')
    # El pooler de Supabase escucha en 6543 en modo transacción: cada sentencia puede caer en
    # una conexión distinta, así que no admite cursores de servidor, sentencias preparadas ni
    # conexiones persistentes del lado de Django. El puerto 5432 sí es una sesión completa.
    pooled = parts.port == 6543
    return {'ENGINE': 'django.db.backends.postgresql', 'NAME': parts.path.lstrip('/') or 'postgres',
            'USER': unquote(parts.username), 'PASSWORD': unquote(parts.password or ''),
            'HOST': parts.hostname, 'PORT': str(parts.port or 5432),
            'CONN_MAX_AGE': 0 if pooled else 600, 'DISABLE_SERVER_SIDE_CURSORS': pooled,
            'OPTIONS': {'sslmode': os.environ.get('DATABASE_SSLMODE', 'require'),
                        **({'prepare_threshold': None} if pooled else {})}}


# Las pruebas nunca tocan la base de producción: el pooler no concede CREATE DATABASE y el
# runner de Django la necesita para crear la base de test.
DATABASE_URL = '' if TESTING else os.environ.get('DATABASE_URL', '')
DATABASES = {'default': postgres(DATABASE_URL) if DATABASE_URL else SQLITE}
AUTHENTICATION_BACKENDS = ['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 15}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=20)
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = 'events.security.locked_out'
AXES_SENSITIVE_PARAMETERS = ['username', 'password']
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
APPEND_SLASH = False
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = os.environ.get('DJANGO_CSRF_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173' if DEBUG else '').split(',') if DEBUG or os.environ.get('DJANGO_CSRF_ORIGINS') else []
CSRF_FAILURE_VIEW = 'events.security.csrf_failure'
# Detrás de un proxy TLS (Render, Fly, Railway, nginx) Django ve la petición como HTTP y
# SECURE_SSL_REDIRECT entraría en un bucle de redirecciones sin esta cabecera.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = not DEBUG and not TESTING
# El chequeo de salud del proveedor no siempre llega con X-Forwarded-Proto, y un 301 lo haría
# marcar el servicio como caído.
SECURE_REDIRECT_EXEMPT = [r'^healthz$']

# Token del disparador externo de tareas (la purga por retención). Sin cron del proveedor, un
# cron gratuito llama al endpoint con este token. Vacío = el endpoint no existe.
TAREAS_TOKEN = os.environ.get('TAREAS_TOKEN', '')
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 3
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# El frontend lo sirve Vercel. Si dist/ existe igualmente (desarrollo, o una imagen todo en
# uno), whitenoise lo sirve también desde aquí; si no, no se declara para no avisar en cada
# arranque por un directorio que no tiene por qué estar.
if (ROOT_DIR / 'dist').is_dir():
    WHITENOISE_ROOT = ROOT_DIR / 'dist'
    WHITENOISE_INDEX_FILE = True
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
PRIVATE_ROOT = BASE_DIR / 'private'
# Almacenamiento de archivos. Sin credenciales de Supabase se usa el disco local, que es lo
# correcto en desarrollo y en las pruebas; en un contenedor efímero hay que configurarlas o
# las portadas y los adjuntos de las inscripciones desaparecen en cada redespliegue.
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
SUPABASE_BUCKET_PUBLIC = os.environ.get('SUPABASE_BUCKET_PUBLIC', 'event-images')
SUPABASE_BUCKET_PRIVATE = os.environ.get('SUPABASE_BUCKET_PRIVATE', 'registration-files')
SUPABASE_SIGNED_URL_TTL = int(os.environ.get('SUPABASE_SIGNED_URL_TTL', '300'))
USE_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) and not TESTING

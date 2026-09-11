#!/bin/bash
set -euo pipefail

cd /app/server

# Con argumentos, ejecuta lo que le pidan y sale: es lo que permite que un cron del proveedor
# lance `purge_expired` con esta misma imagen, sin arrancar gunicorn ni volver a migrar.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Migraciones"
DATABASE_URL="${DATABASE_URL_MIGRATIONS:-${DATABASE_URL:-}}" python manage.py migrate --noinput

echo "==> Estáticos"
mkdir -p "${STATIC_ROOT:-/app/server/staticfiles}"
python manage.py collectstatic --noinput

echo "==> Usuario de panel"
python manage.py ensure_admin

echo "==> Gunicorn"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --access-logfile -

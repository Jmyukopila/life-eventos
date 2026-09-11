"""Prepara datos que ni `migrate` ni `seed_demo` cubren: el usuario de personal
del panel y el SiteSettings listo para recibir inscripciones. Se ejecuta con el
Python del proyecto (.venv) contra la base de datos de prueba (DATABASE_PATH).
No usa SQL a mano: solo el ORM de Django, igual que un management command.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from events.models import SiteSettings  # noqa: E402

STAFF_USERNAME = os.environ['E2E_STAFF_USERNAME']
STAFF_PASSWORD = os.environ['E2E_STAFF_PASSWORD']


def ensure_staff_user():
    User = get_user_model()
    user, created = User.objects.get_or_create(username=STAFF_USERNAME, defaults={'is_staff': True, 'is_active': True})
    user.is_staff = True
    user.is_active = True
    user.set_password(STAFF_PASSWORD)
    user.save()
    print(f"Usuario de personal {'creado' if created else 'actualizado'}: {STAFF_USERNAME}")


def ensure_site_ready():
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    site.organization = os.environ['E2E_ORG']
    site.contact_email = os.environ['E2E_CONTACT_EMAIL']
    site.contact_phone = os.environ['E2E_CONTACT_PHONE']
    site.address = os.environ['E2E_ADDRESS']
    site.privacy_policy = os.environ['E2E_PRIVACY_POLICY']
    site.privacy_version = os.environ['E2E_PRIVACY_VERSION']
    site.retention_days = int(os.environ['E2E_RETENTION_DAYS'])
    site.registration_enabled = True
    site.save()
    assert site.ready, f'SiteSettings no quedó listo: {site.__dict__}'
    print('SiteSettings listo: registration_enabled=True, ready=True')


if __name__ == '__main__':
    ensure_staff_user()
    ensure_site_ready()

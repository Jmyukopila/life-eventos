import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea o actualiza el usuario del panel a partir de DJANGO_ADMIN_USER/DJANGO_ADMIN_PASSWORD.'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_ADMIN_USER', 'admin')
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
        if not password:
            self.stdout.write('DJANGO_ADMIN_PASSWORD vacío: no se creó ni modificó ningún usuario.')
            return
        User = get_user_model()
        user = User.objects.filter(username=username).first() or User(username=username)
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError('Contraseña de administrador inválida: ' + ' '.join(exc.messages))
        user.set_password(password)
        user.is_staff = True
        user.is_active = True
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Usuario de panel "{username}" listo.'))

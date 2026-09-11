from django.core.management.base import BaseCommand, CommandError
from events import retention


class Command(BaseCommand):
    help = 'Muestra registros fuera de retención. --execute elimina registros y sus archivos privados.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true')

    def handle(self, *args, **options):
        self.stdout.write(f'Registros vencidos: {retention.vencidos().count()}')
        if not options['execute']:
            self.stdout.write('Simulación: no se modificó ningún dato. Requiere --execute para aplicar.')
            return
        purgados, fallos = retention.purgar()
        for referencia, error in fallos:
            self.stderr.write(f'No se pudo purgar {referencia}: {error}')
        if fallos:
            raise CommandError(f'{len(fallos)} registro(s) sin purgar. Sus archivos siguen almacenados.')
        self.stdout.write(self.style.SUCCESS(f'Retención aplicada ({purgados}). Los cupos históricos no se modificaron.'))

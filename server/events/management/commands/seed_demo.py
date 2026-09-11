from datetime import datetime
from django.core.management.base import BaseCommand
from events.models import Event, SiteSettings


def question(qid, label, kind='text', required=False, options=None, rules=None, help=''):
    return {'id': qid, 'label': label, 'type': kind, 'required': required, 'options': options or [], 'rules': rules or [], 'help': help, 'accept': 'both'}


class Command(BaseCommand):
    help = 'Crea eventos de ejemplo sin usuarios, registros ni habilitación de datos personales.'

    def handle(self, *args, **options):
        SiteSettings.objects.get_or_create(pk=1)
        common = [question('first_time', '¿Es la primera vez que nos acompañas?', 'radio', True, ['Sí', 'No']), question('notes', '¿Hay algo que debamos saber para recibirte mejor?', 'textarea', help='Opcional. Evita incluir información de salud u otros datos sensibles.')]
        rows = [
            ('Un encuentro que nos acerca', 'Iglesia', '2026-09-26T16:00:00-05:00', 'encuentro', 'Un espacio para encontrarnos, adorar juntos y compartir la Palabra.', 'Hay un lugar para ti. Queremos reunirnos como casa para compartir una tarde de adoración, enseñanza y conversación.\n\nPuedes venir por primera vez, con tus amigos o con toda tu familia. No necesitas pertenecer a un grupo para acompañarnos.\n\nAbrimos las puertas 30 minutos antes. Trae tu Biblia si deseas y ven con tiempo para conocer a otras personas. La entrada es libre; el registro nos ayuda a preparar tu bienvenida.', 250, common),
            ('La vida se comparte mejor', 'Grupos de conexión', '2026-09-30T19:00:00-05:00', 'conexion', 'Encuentra un grupo cercano y comienza a caminar en comunidad.', 'Una mesa, una conversación y personas con quienes compartir la semana. Este encuentro está pensado para quienes desean conocer nuestros grupos de conexión.\n\nSi ya participas en uno, cuéntanos cuál. Si es tu primera vez, te ayudaremos a encontrar un horario que funcione para ti.', 80, [question('member', '¿Ya perteneces a un grupo de conexión?', 'radio', True, ['Sí', 'No'], [{'value': 'No', 'target': 'availability'}]), question('leader', '¿Cómo se llama tu líder de grupo?', required=True), question('availability', '¿Qué horario te funciona mejor?', 'select', True, ['Entre semana en la noche', 'Sábados en la mañana', 'Domingos en la tarde'])]),
            ('Una nueva generación', 'Jóvenes', '2026-10-03T17:00:00-05:00', 'jovenes', 'Una tarde de música, conversaciones honestas y nuevos amigos.', 'Queremos escuchar tus preguntas y compartir una tarde diferente. Tendremos música, actividades en equipo y una conversación sobre propósito.\n\nSi eres menor de edad, tu representante legal debe completar tu inscripción y autorizar tu participación.', 120, common),
            ('Tiempo en familia', 'Familias', '2026-10-10T10:00:00-05:00', 'familias', 'Hagamos una pausa para compartir con quienes más queremos.', 'Un encuentro para jugar, conversar y pasar tiempo juntos. Habrá actividades para compartir en familia.\n\nRegistra a cada participante por separado para reservar su cupo. El registro de los menores debe completarlo su representante legal.', 160, [question('activity', '¿En qué actividad te gustaría participar?', 'select', True, ['Juegos en familia', 'Taller creativo', 'Conversación para padres'])]),
            ('Manos que transforman', 'Servicio', '2026-10-17T08:00:00-05:00', 'servicio', 'Súmate a una jornada de servicio para nuestra comunidad.', 'Vamos a dedicar la mañana a preparar y entregar ayudas junto al equipo de voluntarios. No necesitas experiencia previa.\n\nUsa ropa cómoda y calzado cerrado. Al llegar, te indicaremos el equipo y la actividad en la que puedes apoyar.', 60, [question('team', '¿En qué equipo te gustaría apoyar?', 'radio', True, ['Organización', 'Logística', 'Bienvenida'])]),
            ('Una noche. Una voz.', 'Iglesia', '2026-10-23T19:00:00-05:00', 'adoracion', 'Nos reunimos para dar gracias y adorar con una misma voz.', 'Una noche de adoración en nuestra casa. Dejemos un espacio en la semana para dar gracias, orar y compartir como comunidad.\n\nLa entrada es libre y los cupos son limitados. Puedes venir acompañado; cada persona debe tener su registro.', 220, common),
        ]
        for title, category, date, poster, summary, description, capacity, questions in rows:
            Event.objects.get_or_create(title=title, defaults={'category': category, 'date': datetime.fromisoformat(date), 'cover': f'/posters/{poster}.svg', 'gallery': ['/posters/adoracion.svg', '/posters/conexion.svg'] if poster == 'encuentro' else [], 'summary': summary, 'description': description, 'location': 'Casa Life · Sede principal (ubicación de ejemplo)', 'capacity': capacity, 'status': 'published', 'featured': poster == 'encuentro', 'questions': questions})
        self.stdout.write(self.style.SUCCESS('6 eventos de ejemplo disponibles. Inscripciones deshabilitadas hasta configurar privacidad.'))

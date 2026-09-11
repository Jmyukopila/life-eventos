from django.db import transaction
from django.utils import timezone
from . import storage
from .models import Registration


def vencidos():
    return Registration.objects.filter(expires_at__lt=timezone.now())


def purgar():
    # Borra primero el archivo y solo después la fila. Si el borrado en el almacenamiento falla,
    # la inscripción se queda para que la siguiente pasada lo reintente: quitarla dejaría el
    # adjunto huérfano en el bucket, fuera de su plazo de retención y sin nada que lo referencie.
    purgados, fallos = 0, []
    for record in vencidos().iterator():
        try:
            with transaction.atomic():
                for attachment in record.attachments.all():
                    storage.delete(attachment.storage_name, True)
                record.delete()
            purgados += 1
        except Exception as error:
            fallos.append((record.reference, str(error)))
    return purgados, fallos

import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class SiteSettings(models.Model):
    organization = models.CharField(max_length=200, default='Life')
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=500, blank=True)
    privacy_policy = models.TextField(blank=True)
    privacy_version = models.CharField(max_length=80, default='1')
    retention_days = models.PositiveIntegerField(default=180)
    registration_enabled = models.BooleanField(default=False)

    @property
    def ready(self):
        return bool(self.registration_enabled and self.organization and self.contact_email and self.address and len(self.privacy_policy.strip()) >= 200 and self.privacy_version)


class OrgNode(models.Model):
    KINDS = ['organization', 'congregation', 'network', 'subnetwork', 'group']
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    # Camino "/uuid/uuid/": resuelve «todo lo que cuelga de X» con un prefijo indexado.
    # 255 y no 200: cinco niveles ya ocupan 186 caracteres.
    path = models.CharField(max_length=255, unique=True, editable=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['path']
        constraints = [
            models.UniqueConstraint(fields=['kind'], condition=Q(kind='organization'), name='una_sola_organizacion'),
            models.UniqueConstraint(Lower('name'), 'parent', name='nombre_unico_entre_hermanos'),
        ]
        indexes = [models.Index(fields=['path'])]

    def save(self, *args, **kwargs):
        self.path = (self.parent.path if self.parent else '/') + str(self.id) + '/'
        super().save(*args, **kwargs)

    def descendants(self):
        # Incluye al propio nodo: el prefijo de su path siempre lo cubre a sí mismo.
        return OrgNode.objects.filter(path__startswith=self.path)


class Membership(models.Model):
    ROLES = ['apostol', 'pastor', 'lider_red', 'lider', 'estaca']
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='memberships', on_delete=models.CASCADE)
    node = models.ForeignKey(OrgNode, related_name='memberships', on_delete=models.PROTECT)
    role = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'node'], name='una_membresia_por_nodo')]


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=40)
    summary = models.CharField(max_length=280)
    description = models.TextField()
    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=300)
    capacity = models.PositiveIntegerField(default=100)
    registered = models.PositiveIntegerField(default=0)
    cover = models.CharField(max_length=500)
    gallery = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='draft')
    featured = models.BooleanField(default=False)
    questions = models.JSONField(default=list)
    form_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(OrgNode, related_name='events', on_delete=models.PROTECT, null=False)
    guests = models.ManyToManyField(OrgNode, through='EventGuest', related_name='guest_events', blank=True)

    class Meta:
        ordering = ['date']


class Registration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    request_fingerprint = models.CharField(max_length=64, default='')
    reference = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    is_minor = models.BooleanField(default=False)
    guardian_name = models.CharField(max_length=160, blank=True)
    guardian_email = models.EmailField(blank=True)
    answers = models.JSONField(default=dict)
    question_labels = models.JSONField(default=dict)
    form_snapshot = models.JSONField(default=list)
    privacy_version = models.CharField(max_length=80)
    privacy_snapshot = models.TextField()
    consent_evidence = models.JSONField(default=dict)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['event', 'email', 'name'], name='one_person_per_event')]


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(Registration, related_name='attachments', on_delete=models.CASCADE)
    question_id = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    storage_name = models.CharField(max_length=80)
    content_type = models.CharField(max_length=80)


class EventGuest(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    node = models.ForeignKey(OrgNode, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'node'], name='invitado_unico_por_evento')]

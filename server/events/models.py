import uuid
from django.db import models


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

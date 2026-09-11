import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=160)),
                ('category', models.CharField(max_length=40)),
                ('summary', models.CharField(max_length=280)),
                ('description', models.TextField()),
                ('date', models.DateTimeField()),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('location', models.CharField(max_length=300)),
                ('capacity', models.PositiveIntegerField(default=100)),
                ('registered', models.PositiveIntegerField(default=0)),
                ('cover', models.CharField(max_length=500)),
                ('gallery', models.JSONField(default=list)),
                ('status', models.CharField(default='draft', max_length=20)),
                ('featured', models.BooleanField(default=False)),
                ('questions', models.JSONField(default=list)),
                ('form_version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['date'],
            },
        ),
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization', models.CharField(default='Life', max_length=200)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=40)),
                ('address', models.CharField(blank=True, max_length=500)),
                ('privacy_policy', models.TextField(blank=True)),
                ('privacy_version', models.CharField(default='1', max_length=80)),
                ('retention_days', models.PositiveIntegerField(default=180)),
                ('registration_enabled', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_id', models.UUIDField(unique=True)),
                ('reference', models.CharField(max_length=30, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=160)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=40)),
                ('is_minor', models.BooleanField(default=False)),
                ('guardian_name', models.CharField(blank=True, max_length=160)),
                ('guardian_email', models.EmailField(blank=True, max_length=254)),
                ('answers', models.JSONField(default=dict)),
                ('question_labels', models.JSONField(default=dict)),
                ('form_snapshot', models.JSONField(default=list)),
                ('privacy_version', models.CharField(max_length=80)),
                ('privacy_snapshot', models.TextField()),
                ('consent_evidence', models.JSONField(default=dict)),
                ('expires_at', models.DateTimeField()),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='events.event')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('question_id', models.CharField(max_length=80)),
                ('name', models.CharField(max_length=255)),
                ('storage_name', models.CharField(max_length=80)),
                ('content_type', models.CharField(max_length=80)),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='events.registration')),
            ],
        ),
        migrations.AddConstraint(
            model_name='registration',
            constraint=models.UniqueConstraint(fields=('event', 'email', 'name'), name='one_person_per_event'),
        ),
    ]

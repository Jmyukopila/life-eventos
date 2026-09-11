from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='request_fingerprint',
            field=models.CharField(default='', max_length=64),
        ),
    ]

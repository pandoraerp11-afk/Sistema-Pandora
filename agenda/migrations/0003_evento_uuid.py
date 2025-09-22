from django.db import migrations, models
import uuid


def populate_evento_uuid(apps, schema_editor):
    Evento = apps.get_model('agenda', 'Evento')
    for ev in Evento.objects.filter(uuid__isnull=True):  # type: ignore
        ev.uuid = uuid.uuid4()
        try:
            ev.save(update_fields=['uuid'])
        except Exception:
            pass


class Migration(migrations.Migration):
    dependencies = [
        ('agenda', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evento',
            name='uuid',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
        migrations.RunPython(populate_evento_uuid, migrations.RunPython.noop),
    ]

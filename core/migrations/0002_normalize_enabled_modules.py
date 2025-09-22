from django.db import migrations
import json

def normalize_enabled_modules(apps, schema_editor):
    Tenant = apps.get_model('core', 'Tenant')
    for tenant in Tenant.objects.all():
        raw = tenant.enabled_modules
        normalized = []
        try:
            if isinstance(raw, dict):
                if 'modules' in raw and isinstance(raw['modules'], (list, tuple)):
                    normalized = list(dict.fromkeys(raw['modules']))
                else:
                    normalized = [k for k,v in raw.items() if v in (True, 1, 'on')]
            elif isinstance(raw, (list, tuple)):
                normalized = list(dict.fromkeys(raw))
            elif isinstance(raw, str):
                # tentar interpretar como json; senão split por vírgula
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        normalized = list(dict.fromkeys(parsed))
                    elif isinstance(parsed, dict) and 'modules' in parsed:
                        normalized = list(dict.fromkeys(parsed['modules']))
                except Exception:
                    normalized = [m.strip() for m in raw.replace(';', ',').split(',') if m.strip()]
        except Exception:
            normalized = []
        # Persistir no formato canonical: {"modules": [..]}
        tenant.enabled_modules = {"modules": normalized}
        tenant.save(update_fields=['enabled_modules'])

def reverse_noop(apps, schema_editor):
    # Não reverte (one-way). Poderia armazenar backup externo se necessário.
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_enabled_modules, reverse_noop),
    ]

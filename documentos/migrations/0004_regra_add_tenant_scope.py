from django.db import migrations, models
import django.db.models.deletion

def forwards(apps, schema_editor):
    Regra = apps.get_model('documentos', 'RegraDocumento')
    # Nada especial além de manter coerência: regras globais ficam com tenant null
    # Se alguma regra tinha escopo 'app' e por algum motivo tenant preenchido (não existia campo), ignorar.
    for r in Regra.objects.all():
        # Garantir consistência: se escopo='tenant' (ainda não existirá) não fazer nada.
        pass

def backwards(apps, schema_editor):
    # Nada para reverter além de remoção automática do campo pelo framework.
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('core','0001_initial'),
        ('documentos','0003_rename_documentos_regra_status_idx_documentos__status_c37e99_idx_and_more'),
    ]
    operations = [
        migrations.AddField(
            model_name='regradocumento',
            name='tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='regras_documento', to='core.tenant', verbose_name='Tenant'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
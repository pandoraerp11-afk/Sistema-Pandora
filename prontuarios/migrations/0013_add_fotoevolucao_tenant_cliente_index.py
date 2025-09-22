from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('prontuarios', '0012_atendimento_agendamento'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='fotoevolucao',
            index=models.Index(fields=['tenant', 'cliente'], name='pront_foto_tenant_cliente_idx'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prontuarios', '0006_fotoevolucao_derivados_indices'),
    ]

    operations = [
        migrations.AddField(
            model_name='fotoevolucao',
            name='video_meta',
            field=models.JSONField(blank=True, null=True, help_text='Metadados e status de validação/transcodificação do vídeo'),
        ),
    ]

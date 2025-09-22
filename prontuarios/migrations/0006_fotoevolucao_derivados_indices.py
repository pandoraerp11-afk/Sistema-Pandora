from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prontuarios', '0005_alter_atendimentodisponibilidade_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='fotoevolucao',
            name='imagem_webp',
            field=models.ImageField(blank=True, null=True, upload_to='prontuarios/webp/', help_text='Versão otimizada WEBP'),
        ),
        migrations.AddField(
            model_name='fotoevolucao',
            name='video_poster',
            field=models.ImageField(blank=True, null=True, upload_to='prontuarios/videos_posters/', help_text='Frame de pré-visualização extraído do vídeo'),
        ),
        migrations.AddIndex(
            model_name='fotoevolucao',
            index=models.Index(fields=['tenant', 'data_foto'], name='prontuario_foto_tenant_data_idx'),
        ),
        migrations.AddIndex(
            model_name='fotoevolucao',
            index=models.Index(fields=['tenant', 'paciente', 'data_foto'], name='prontuario_foto_tenant_paciente_data_idx'),
        ),
    ]

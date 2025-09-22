from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('user_management', '0007_perfilusuarioestendido_twofa_rate_limit_block_count'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='perfilusuarioestendido',
            index=models.Index(fields=['status'], name='perfil_status_idx'),
        ),
        migrations.AddIndex(
            model_name='perfilusuarioestendido',
            index=models.Index(fields=['tipo_usuario'], name='perfil_tipo_idx'),
        ),
        migrations.AddIndex(
            model_name='perfilusuarioestendido',
            index=models.Index(fields=['twofa_locked_until'], name='perfil_twofa_locked_idx'),
        ),
    ]
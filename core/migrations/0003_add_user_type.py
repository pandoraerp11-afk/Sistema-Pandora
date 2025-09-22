from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0002_normalize_enabled_modules'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='user_type',
            field=models.CharField(choices=[('INTERNAL', 'Interno'), ('PORTAL', 'Portal Externo')], db_index=True, default='INTERNAL', max_length=20, verbose_name='Tipo de Usuário'),
        ),
    ]

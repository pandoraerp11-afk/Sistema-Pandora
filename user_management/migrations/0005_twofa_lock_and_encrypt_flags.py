from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0004_perfilusuarioestendido_failed_2fa_attempts_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuarioestendido',
            name='twofa_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='perfilusuarioestendido',
            name='twofa_secret_encrypted',
            field=models.BooleanField(default=False),
        ),
    ]
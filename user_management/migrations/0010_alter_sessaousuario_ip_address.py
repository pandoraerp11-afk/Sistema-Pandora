from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('user_management', '0009_alter_logatividadeusuario_ip_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sessaousuario',
            name='ip_address',
            field=models.GenericIPAddressField(null=True, blank=True, default=None),
        ),
    ]

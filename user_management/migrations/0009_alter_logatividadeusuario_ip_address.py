from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('user_management', '0008_auto_add_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='logatividadeusuario',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, default='0.0.0.0'),
        ),
    ]

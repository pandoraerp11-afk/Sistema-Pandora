from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_alter_role_tenant_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Ativo'),
        ),
    ]

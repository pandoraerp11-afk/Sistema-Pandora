from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_department_tenant_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='tenant',
            field=models.ForeignKey(null=True, blank=True, to='core.tenant', on_delete=models.deletion.CASCADE, related_name='roles', verbose_name='Empresa'),
        ),
    ]

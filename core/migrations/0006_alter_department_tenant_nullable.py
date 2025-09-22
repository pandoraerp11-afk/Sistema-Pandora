from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_role_department_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='department',
            name='tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name='departments', to='core.tenant', verbose_name='Empresa'),
        ),
    ]

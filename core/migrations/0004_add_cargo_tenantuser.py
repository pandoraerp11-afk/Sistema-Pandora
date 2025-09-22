from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_add_user_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantuser',
            name='cargo',
            field=models.CharField(max_length=120, blank=True, null=True, verbose_name='Cargo / Função'),
        ),
    ]

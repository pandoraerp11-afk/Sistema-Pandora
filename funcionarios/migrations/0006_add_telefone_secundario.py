from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0005_add_rg_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='telefone_secundario',
            field=models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefone Secundário'),
        ),
    ]

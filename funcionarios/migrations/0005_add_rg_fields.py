from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0004_add_ident_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='rg_orgao_emissor',
            field=models.CharField(max_length=20, blank=True, null=True, verbose_name='Órgão Emissor RG'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='rg_data_emissao',
            field=models.DateField(blank=True, null=True, verbose_name='Data Emissão RG'),
        ),
    ]

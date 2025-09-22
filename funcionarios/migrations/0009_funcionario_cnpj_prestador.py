from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0008_funcionariohorario'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='cnpj_prestador',
            field=models.CharField(blank=True, max_length=18, null=True, verbose_name='CNPJ (Prestador PJ/MEI)'),
        ),
    ]

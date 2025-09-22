from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0009_funcionario_cnpj_prestador'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='pj_categoria',
            field=models.CharField(blank=True, choices=[('MEI','MEI'),('SOCIEDADE','Sociedade / Empresa'),('AUTONOMO','Autônomo (RPA)')], max_length=20, null=True, verbose_name='Categoria PJ'),
        ),
    ]

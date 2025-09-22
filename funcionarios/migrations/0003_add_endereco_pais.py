from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0002_configuracaomaterial_crachafuncionario_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='endereco_pais',
            field=models.CharField(blank=True, default='Brasil', max_length=100, null=True, verbose_name='País'),
        ),
    ]

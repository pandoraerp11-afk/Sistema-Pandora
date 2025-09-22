from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0003_add_endereco_pais'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='naturalidade',
            field=models.CharField(blank=True, null=True, max_length=100, verbose_name='Naturalidade (Cidade de Nascimento)'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='nome_mae',
            field=models.CharField(blank=True, null=True, max_length=255, verbose_name='Nome da Mãe'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='nome_pai',
            field=models.CharField(blank=True, null=True, max_length=255, verbose_name='Nome do Pai'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='profissao',
            field=models.CharField(blank=True, null=True, max_length=150, verbose_name='Profissão'),
        ),
    ]

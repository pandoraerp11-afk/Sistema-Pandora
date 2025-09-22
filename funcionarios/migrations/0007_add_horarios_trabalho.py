from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0006_add_telefone_secundario'),
    ]

    operations = [
        migrations.AddField(
            model_name='funcionario',
            name='horario_entrada',
            field=models.TimeField(blank=True, null=True, verbose_name='Horário de Entrada'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='horario_saida',
            field=models.TimeField(blank=True, null=True, verbose_name='Horário de Saída'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='intervalo_inicio',
            field=models.TimeField(blank=True, null=True, verbose_name='Início Intervalo'),
        ),
        migrations.AddField(
            model_name='funcionario',
            name='intervalo_fim',
            field=models.TimeField(blank=True, null=True, verbose_name='Fim Intervalo'),
        ),
    ]

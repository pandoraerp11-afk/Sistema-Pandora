from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0010_funcionario_pj_categoria'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuncionarioRemuneracaoRegra',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de atualização')),
                ('tipo_regra', models.CharField(choices=[('FIXO_MENSAL', 'Salário Fixo Mensal'), ('HORA', 'Valor por Hora'), ('TAREFA', 'Valor por Tarefa'), ('PROCEDIMENTO_PERCENTUAL', '% sobre Procedimento'), ('PROCEDIMENTO_FIXO', 'Valor Fixo por Procedimento'), ('COMISSAO_PERCENTUAL', '% de Comissão'), ('COMISSAO_FIXA', 'Comissão Fixa')], max_length=40, verbose_name='Tipo de Regra')),
                ('descricao', models.CharField(blank=True, max_length=255, null=True, verbose_name='Descrição')),
                ('valor_base', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Valor Base')),
                ('percentual', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Percentual (%)')),
                ('codigo_procedimento', models.CharField(blank=True, max_length=100, null=True, verbose_name='Código Procedimento (Opcional)')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('vigencia_inicio', models.DateField(blank=True, null=True, verbose_name='Início Vigência')),
                ('vigencia_fim', models.DateField(blank=True, null=True, verbose_name='Fim Vigência')),
                ('funcionario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regras_remuneracao', to='funcionarios.funcionario', verbose_name='Funcionário')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regras_remuneracao', to='core.tenant', verbose_name='Empresa')),
            ],
            options={'verbose_name': 'regra de remuneração', 'verbose_name_plural': 'regras de remuneração', 'ordering': ['funcionario', 'tipo_regra', '-vigencia_inicio']},
        ),
    ]

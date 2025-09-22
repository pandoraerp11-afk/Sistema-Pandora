from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('funcionarios', '0007_add_horarios_trabalho'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuncionarioHorario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.IntegerField(choices=[(0, 'Segunda'), (1, 'Terça'), (2, 'Quarta'), (3, 'Quinta'), (4, 'Sexta'), (5, 'Sábado'), (6, 'Domingo')])),
                ('ordem', models.PositiveSmallIntegerField(default=1, help_text='Permite múltiplos blocos no mesmo dia (1 = principal)')),
                ('entrada', models.TimeField(blank=True, null=True)),
                ('saida', models.TimeField(blank=True, null=True)),
                ('intervalo_inicio', models.TimeField(blank=True, null=True)),
                ('intervalo_fim', models.TimeField(blank=True, null=True)),
                ('horas_previstas', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('ativo', models.BooleanField(default=True)),
                ('funcionario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='horarios', to='funcionarios.funcionario')),
            ],
            options={'ordering': ['funcionario', 'dia_semana', 'ordem']},
        ),
        migrations.AlterUniqueTogether(name='funcionariohorario', unique_together={('funcionario', 'dia_semana', 'ordem')}),
    ]

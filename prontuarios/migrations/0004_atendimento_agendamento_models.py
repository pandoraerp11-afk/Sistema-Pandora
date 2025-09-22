# Generated migration for scheduling enhancements
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('agenda', '0001_initial'),
        ('prontuarios', '0003_anamnese_cliente_atendimento_cliente_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='atendimento',
            name='evento_agenda',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='atendimentos', to='agenda.evento', help_text='Evento na agenda associado'),
        ),
        migrations.AddField(
            model_name='atendimento',
            name='origem_agendamento',
            field=models.CharField(choices=[('CLIENTE','Cliente'),('PROFISSIONAL','Profissional'),('SECRETARIA','Secretaria'),('SISTEMA','Sistema')], default='PROFISSIONAL', max_length=20),
        ),
        migrations.CreateModel(
            name='AtendimentoDisponibilidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('data', models.DateField()),
                ('hora_inicio', models.TimeField()),
                ('hora_fim', models.TimeField()),
                ('duracao_slot_minutos', models.PositiveIntegerField(default=30, help_text='Granularidade dos slots gerados')),
                ('capacidade_por_slot', models.PositiveIntegerField(default=1)),
                ('recorrente', models.BooleanField(default=False)),
                ('regra_recorrencia', models.CharField(blank=True, null=True, max_length=50, help_text='Ex: WEEKLY, BIWEEKLY')),
                ('ativo', models.BooleanField(default=True)),
                ('profissional', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disponibilidades_atendimento', to='core.customuser')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='atendimentos_disponibilidades', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Disponibilidade de Atendimento',
                'verbose_name_plural': 'Disponibilidades de Atendimento',
            },
        ),
        migrations.CreateModel(
            name='AtendimentoSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('horario', models.DateTimeField()),
                ('capacidade_total', models.PositiveIntegerField(default=1)),
                ('capacidade_utilizada', models.PositiveIntegerField(default=0)),
                ('ativo', models.BooleanField(default=True)),
                ('disponibilidade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slots', to='prontuarios.atendimentodisponibilidade')),
                ('profissional', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slots_atendimento', to='core.customuser')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='atendimentos_slots', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Slot de Atendimento',
                'verbose_name_plural': 'Slots de Atendimento',
                'ordering': ['horario'],
            },
        ),
        migrations.AddField(
            model_name='atendimento',
            name='slot',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='atendimentos', to='prontuarios.atendimentoslot', help_text='Slot reservado da agenda clínica'),
        ),
        migrations.AddConstraint(
            model_name='atendimentodisponibilidade',
            constraint=models.UniqueConstraint(fields=('tenant','profissional','data','hora_inicio','hora_fim'), name='unique_disponibilidade_intervalo_profissional'),
        ),
        migrations.AddConstraint(
            model_name='atendimentoslot',
            constraint=models.UniqueConstraint(fields=('profissional','horario'), name='unique_slot_profissional_horario'),
        ),
    ]

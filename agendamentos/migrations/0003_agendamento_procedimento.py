from django.db import migrations, models
import django.db.models.deletion


def map_tipo_servico_to_procedimento(apps, schema_editor):
    Agendamento = apps.get_model('agendamentos','Agendamento')
    Procedimento = apps.get_model('prontuarios','Procedimento')
    for ag in Agendamento.objects.filter(procedimento__isnull=True).exclude(tipo_servico__isnull=True).exclude(tipo_servico__exact='')[:10000]:
        proc = Procedimento.objects.filter(nome__iexact=ag.tipo_servico.strip(), tenant=ag.tenant).first()
        if proc:
            ag.procedimento_id = proc.id
            # Se duração não casa, não ajustamos retroativamente
            ag.save(update_fields=['procedimento'])

class Migration(migrations.Migration):
    dependencies = [
        ('prontuarios','0001_initial'),
        ('agendamentos','0002_waitlist_overbooking'),
    ]

    operations = [
        migrations.AddField(
            model_name='agendamento',
            name='procedimento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agendamentos', help_text='Procedimento clínico associado (fase transição)', to='prontuarios.procedimento'),
        ),
        migrations.RunPython(map_tipo_servico_to_procedimento, migrations.RunPython.noop),
    ]

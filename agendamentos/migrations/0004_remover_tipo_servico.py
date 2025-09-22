from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('agendamentos','0003_agendamento_procedimento'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agendamento',
            name='tipo_servico',
        ),
    ]

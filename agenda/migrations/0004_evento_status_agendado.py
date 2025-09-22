from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('agenda', '0003_evento_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evento',
            name='status',
            field=models.CharField(choices=[('agendado', 'Agendado'), ('pendente', 'Pendente'), ('confirmado', 'Confirmado'), ('realizado', 'Realizado'), ('concluido', 'Concluído'), ('cancelado', 'Cancelado')], default='agendado', max_length=10, verbose_name='Status'),
        ),
    ]

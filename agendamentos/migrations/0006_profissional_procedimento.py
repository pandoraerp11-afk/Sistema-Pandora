from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('agendamentos', '0005_alter_agendamento_procedimento'),
        ('prontuarios', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfissionalProcedimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ativo', models.BooleanField(default=True)),
                ('procedimento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profissionais_habilitados', to='prontuarios.procedimento')),
                ('profissional', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competencias_procedimento', to='core.customuser')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='competencias_prof_proc', to='core.tenant')),
            ],
            options={
                'verbose_name': 'Competência do Profissional em Procedimento',
                'verbose_name_plural': 'Competências de Profissionais em Procedimentos',
            },
        ),
        migrations.AddIndex(
            model_name='profissionalprocedimento',
            index=models.Index(fields=['tenant', 'profissional'], name='agendam_profc_tenant_prof_idx'),
        ),
        migrations.AddIndex(
            model_name='profissionalprocedimento',
            index=models.Index(fields=['tenant', 'procedimento'], name='agendam_profc_tenant_proc_idx'),
        ),
        migrations.AddConstraint(
            model_name='profissionalprocedimento',
            constraint=models.UniqueConstraint(fields=('tenant', 'profissional', 'procedimento'), name='uniq_competencia_prof_procedimento'),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('documentos', '0005_alter_regradocumento_escopo'),
    ]

    operations = [
        migrations.CreateModel(
            name='WizardTenantDocumentoTemp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, help_text='Chave de sessão antes de existir tenant', max_length=64, null=True)),
                ('obrigatorio_snapshot', models.BooleanField(default=False)),
                ('nome_tipo_cache', models.CharField(max_length=120)),
                ('arquivo', models.FileField(upload_to='wizard_docs_temp/')),
                ('filename_original', models.CharField(blank=True, max_length=255)),
                ('tamanho_bytes', models.PositiveIntegerField(default=0)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wizard_docs_temp', to='core.tenant')),
                ('tipo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wizard_temp_docs', to='documentos.tipodocumento')),
            ],
            options={
                'verbose_name': 'Documento Temporário (Wizard)',
                'verbose_name_plural': 'Documentos Temporários (Wizard)',
            },
        ),
        migrations.AddIndex(
            model_name='wizardtenantdocumentotemp',
            index=models.Index(fields=['tenant', 'session_key'], name='documentos_tenant_sess_idx'),
        ),
        migrations.AddIndex(
            model_name='wizardtenantdocumentotemp',
            index=models.Index(fields=['tipo'], name='documentos_tipo_idx'),
        ),
    ]

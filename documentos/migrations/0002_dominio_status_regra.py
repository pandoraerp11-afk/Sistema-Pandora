from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    RegraDocumento = apps.get_model('documentos', 'RegraDocumento')
    DominioDocumento = apps.get_model('documentos', 'DominioDocumento')
    # Criar dominios distintos a partir de app_label existentes
    labels = set(RegraDocumento.objects.exclude(app_label__isnull=True).exclude(app_label='').values_list('app_label', flat=True))
    slugify = lambda s: s.lower().replace(' ', '-').replace('_','-')
    mapa = {}
    for lbl in labels:
        d = DominioDocumento.objects.create(nome=lbl.title(), slug=slugify(lbl), app_label=lbl)
        mapa[lbl] = d.id
    # Atribuir dominio às regras
    for regra in RegraDocumento.objects.all():
        if regra.app_label and regra.app_label in mapa:
            regra.dominio_id = mapa[regra.app_label]
            # Migrar para status 'aprovada' conservando ativo
            regra.status = 'aprovada' if regra.ativo else 'inativa'
            regra.save(update_fields=['dominio_id','status'])


def backwards(apps, schema_editor):
    # Nada reversível sem perda, manter vazio.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DominioDocumento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Nome do Domínio')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Slug')),
                ('app_label', models.CharField(max_length=50, verbose_name='App Label')),
                ('descricao', models.CharField(blank=True, max_length=255, verbose_name='Descrição')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Domínio de Documento',
                'verbose_name_plural': 'Domínios de Documento',
                'ordering': ['nome'],
            },
        ),
        migrations.AddField(
            model_name='regradocumento',
            name='dominio',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regras', to='documentos.dominiodocumento', verbose_name='Domínio'),
        ),
        migrations.AddField(
            model_name='regradocumento',
            name='status',
            field=models.CharField(choices=[('rascunho', 'Rascunho'), ('pendente', 'Pendente Aprovação'), ('aprovada', 'Aprovada'), ('inativa', 'Inativada')], default='aprovada', max_length=20, verbose_name='Status'),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AddIndex(
            model_name='regradocumento',
            index=models.Index(fields=['status'], name='documentos_regra_status_idx'),
        ),
        migrations.AddIndex(
            model_name='regradocumento',
            index=models.Index(fields=['dominio'], name='documentos_regra_dominio_idx'),
        ),
    ]

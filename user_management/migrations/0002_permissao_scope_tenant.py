from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('user_management', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='permissaopersonalizada',
            name='scope_tenant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='permissoes_personalizadas', to='core.tenant'),
        ),
        migrations.AlterUniqueTogether(
            name='permissaopersonalizada',
            unique_together={('user', 'modulo', 'acao', 'recurso', 'scope_tenant')},
        ),
        migrations.AddIndex(
            model_name='permissaopersonalizada',
            index=models.Index(fields=['user', 'scope_tenant', 'modulo', 'acao'], name='perm_user_scope_mod_action_idx'),
        ),
    ]

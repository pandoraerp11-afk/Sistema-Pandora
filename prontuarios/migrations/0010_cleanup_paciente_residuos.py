from django.db import migrations, models


def drop_old_paciente_columns(apps, schema_editor):
    """Limpeza de resíduos de 'paciente': remove índices órfãos se existirem.
    Evita falha em ambiente onde já foram removidos.
    """
    cursor = schema_editor.connection.cursor()
    try:
        cursor.execute("DROP INDEX IF EXISTS prontuario_foto_tenant_paciente_data_idx;")
    except Exception:
        pass
    try:
        cursor.execute("DROP INDEX IF EXISTS prontuarios_tenant__3b2fcc_idx;")
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("prontuarios", "0009_remove_paciente_tenant_remove_anamnese_paciente_and_more"),
    ]

    operations = [
        migrations.RunPython(drop_old_paciente_columns, migrations.RunPython.noop),
    ]

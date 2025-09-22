from django.db import migrations


def rename_paciente_to_cliente(apps, schema_editor):
    """Se ainda existir coluna paciente_id na tabela de foto evolução, cria cliente_id e copia os valores.
    Remove índice antigo baseado em paciente.
    """
    cursor = schema_editor.connection.cursor()
    try:
        cursor.execute("PRAGMA table_info(prontuarios_fotoevolucao);")
        cols = [row[1] for row in cursor.fetchall()]
        if 'paciente_id' in cols and 'cliente_id' not in cols:
            cursor.execute("ALTER TABLE prontuarios_fotoevolucao ADD COLUMN cliente_id INTEGER;")
            try:
                cursor.execute("UPDATE prontuarios_fotoevolucao SET cliente_id = paciente_id WHERE cliente_id IS NULL;")
            except Exception:
                pass
        # Drop índice antigo
        try:
            cursor.execute("DROP INDEX IF EXISTS prontuario_foto_tenant_paciente_data_idx;")
        except Exception:
            pass
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("prontuarios", "0010_cleanup_paciente_residuos"),
        ("clientes", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(rename_paciente_to_cliente, migrations.RunPython.noop),
    ]

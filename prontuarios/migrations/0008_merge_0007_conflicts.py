from django.db import migrations

class Migration(migrations.Migration):
    """Merge de migrations conflitantes 0007.* unificando grafo.
    Certifica que ambas as alterações (renome de índices/campos e video_meta) sejam aplicadas.
    """
    dependencies = [
        ('prontuarios', '0007_fotoevolucao_video_meta'),
        ('prontuarios', '0007_rename_prontuario_foto_tenant_data_idx_prontuarios_tenant__6dcd04_idx_and_more'),
    ]

    operations = []

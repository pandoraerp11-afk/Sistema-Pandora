# cadastros_gerais/tables.py
import django_tables2 as tables

from .models import UnidadeMedida


class UnidadeMedidaTable(tables.Table):
    # Coluna personalizada para os botões de ação
    acoes = tables.TemplateColumn(
        template_name="cadastros_gerais/coluna_acoes.html",
        verbose_name="Ações",
        orderable=False,
        # --- ALTERAÇÃO APLICADA AQUI ---
        # Adiciona um atributo à célula da tabela (<td>) para alinhar o conteúdo à direita.
        attrs={"td": {"class": "text-right"}},
    )

    class Meta:
        model = UnidadeMedida
        fields = ("nome", "simbolo", "acoes")
        attrs = {"class": "table table-hover table-striped"}
        template_name = "django_tables2/bootstrap5.html"

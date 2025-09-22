# compras/tables.py CORRIGIDO
import django_tables2 as tables

from .models import Compra  # Certifique-se que o modelo Compra está corretamente importado


class CompraTable(tables.Table):
    """
    Tabela para exibição de compras com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # Coluna para o número da compra, que também será um link para os detalhes.
    # Assumindo que 'numero' é um campo no seu modelo Compra.
    numero = tables.LinkColumn(
        "compras:compra_detail",  # Nome da URL para a view de detalhes da compra.
        args=[tables.A("pk")],  # Passa a chave primária (pk) da compra para a URL.
        accessor="numero",  # Acessa o atributo 'numero' do objeto Compra.
        verbose_name="Número",  # Texto do cabeçalho da coluna.
    )

    # Coluna para o fornecedor. Usa o accessor para buscar o nome através da ForeignKey.
    # Supondo que seu modelo Compra tem um campo ForeignKey 'fornecedor'
    # e o modelo Fornecedor tem um campo 'nome_empresa' (ou 'nome' se for o caso).
    # O erro anterior do módulo fornecedores indicava 'nome_empresa'.
    fornecedor = tables.Column(
        accessor="fornecedor__nome_empresa",  # Ajuste se o campo no modelo Fornecedor for diferente
        verbose_name="Fornecedor",
    )

    # Coluna para a obra. Usa o accessor para buscar o nome através da ForeignKey.
    # Supondo que seu modelo Compra tem um campo ForeignKey 'obra'
    # e o modelo Obra tem um campo 'nome' (ou similar).
    obra = tables.Column(
        accessor="obra__nome",  # Ajuste se o campo no modelo Obra for diferente
        verbose_name="Obra",
    )

    # Coluna para o status da compra.
    # Assumindo que seu modelo Compra tem um campo 'status' com os valores esperados.
    status = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'pendente' %}
            <span class="badge bg-warning">Pendente</span>
        {% elif record.status == 'aprovada' %}
            <span class="badge bg-success">Aprovada</span>
        {% elif record.status == 'recebida' %}
            <span class="badge bg-info">Recebida</span>
        {% elif record.status == 'cancelada' %}
            <span class="badge bg-danger">Cancelada</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status }}</span>
        {% endif %}
        """,
        verbose_name="Status",
        accessor="status",  # Permite ordenação pelo campo 'status'
    )

    # Coluna de Ações com botões para Editar e Excluir.
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'compras:compra_edit' record.pk %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'compras:compra_delete' record.pk %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    class Meta:
        model = Compra
        template_name = "django_tables2/bootstrap5.html"

        # Liste os campos/colunas na ordem que você quer que apareçam.
        # Use 'data_pedido' em vez de 'data_compra'.
        fields = (
            "id",
            "numero",
            "fornecedor",
            "obra",
            "data_pedido",  # CORRIGIDO de 'data_compra'
            "data_entrega_prevista",  # Mantido, pois existe no modelo
            "valor_total",
            "status",
            "acoes",  # Adicionando a coluna de ações
        )

        attrs = {
            "class": "table table-striped table-hover table-bordered",
            "id": "compras-table",  # ID da tabela, útil para JavaScript (ex: DataTables).
        }

        row_attrs = {"data-id": lambda record: record.pk}

        # Define a ordenação padrão da tabela.
        order_by = ("-data_pedido",)  # CORRIGIDO de '-data_compra'

# estoque/tables.py

import django_tables2 as tables

from produtos.models import Produto

# CORREÇÃO 1: Importar o modelo com o nome correto ('Movimento' em vez de 'MovimentacaoEstoque')
from .models_movimento import Movimento


class ProdutoTable(tables.Table):
    """
    Tabela para exibição de produtos com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # Adiciona coluna de ações com botões de editar e excluir
    acoes = tables.TemplateColumn(
        template_code=""",
        <div class="btn-group">
            <a href="{% url 'estoque:produto_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'estoque:produto_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # Personaliza a coluna de nome para incluir um link para a página de detalhes
    nome = tables.LinkColumn("estoque:produto_detail", args=[tables.A("pk")], attrs={"a": {"class": "produto-link"}})

    # Personaliza a coluna de status para exibir um badge colorido
    status_ciclo = tables.TemplateColumn(
        template_code=""",
        {% if record.status_ciclo == 'ATIVO' %}
            <span class="badge bg-success">Ativo</span>
        {% elif record.status_ciclo == 'SUSPENSO' %}
            <span class="badge bg-warning">Suspenso</span>
        {% elif record.status_ciclo == 'DESCONTINUADO' %}
            <span class="badge bg-danger">Descontinuado</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status_ciclo }}</span>
        {% endif %}
        """,
        verbose_name="Status",
    )

    # Coluna calculada de preço de venda (derivada de custo + margem)
    preco_venda = tables.Column(verbose_name="Preço Venda")

    def render_preco_venda(self, record):
        try:
            valor = record.calcular_preco_venda()
            return f"{valor:.2f}"
        except Exception:
            return "-"

    # Personaliza a coluna de estoque para exibir um badge colorido baseado no nível
    estoque_atual = tables.TemplateColumn(
        template_code=""",
        {% if record.estoque_atual <= record.estoque_minimo %}
            <span class="badge bg-danger">{{ record.estoque_atual }}</span>
        {% elif record.estoque_atual <= record.estoque_minimo|add:5 %}
            <span class="badge bg-warning">{{ record.estoque_atual }}</span>
        {% else %}
            <span class="badge bg-success">{{ record.estoque_atual }}</span>
        {% endif %}
        """,
        verbose_name="Estoque Atual",
    )

    class Meta:
        model = Produto
        template_name = "django_tables2/bootstrap5.html"
        # Inclui preco_unitario real do modelo e preco_venda calculado
        fields = (
            "id",
            "codigo",
            "nome",
            "categoria",
            "unidade",
            "preco_custo",
            "preco_unitario",
            "preco_venda",
            "estoque_atual",
            "estoque_minimo",
            "status_ciclo",
        )
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "produtos-table"}
        row_attrs = {
            "data-id": lambda record: record.pk,
            "class": lambda record: "table-danger"
            if record.estoque_atual <= record.estoque_minimo
            else "table-warning"
            if record.estoque_atual <= record.estoque_minimo + 5
            else "",
        }
        order_by = ("nome",)  # Ordenação padrão


## EstoqueTable legado removido (ItemEstoque excluído)


# CORREÇÃO 2: Renomeada a classe da tabela para 'MovimentoTable' para consistência
class MovimentoTable(tables.Table):
    """
    Tabela para exibição de movimentos de estoque com suporte a ordenação, filtragem e paginação.
    """

    acoes = tables.TemplateColumn(
        template_code=""",
        <div class="btn-group">
            <a href="{% url 'estoque:movimento_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'estoque:movimento_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # django-tables2: usar '__' em vez de '.' para evitar deprecation
    produto = tables.Column(accessor="produto__nome", verbose_name="Produto")

    tipo = tables.TemplateColumn(
        template_code=""",
        {% if record.tipo == 'entrada' %}
            <span class="badge bg-success">Entrada</span>
        {% elif record.tipo == 'saida' %}
            <span class="badge bg-danger">Saída</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.tipo }}</span>
        {% endif %}
        """,
        verbose_name="Tipo",
    )

    quantidade = tables.Column(
        attrs={"td": {"class": lambda value, record: "text-success" if record.tipo == "entrada" else "text-danger"}},
        verbose_name="Quantidade",
    )

    class Meta:
        # CORREÇÃO 4: 'model' ajustado para a classe correta 'Movimento'
        model = Movimento
        template_name = "django_tables2/bootstrap5.html"
        # CORREÇÃO 5: Removido o campo 'responsavel' que não existe no modelo 'Movimento'
        # e adicionado o campo 'acoes'
        fields = ("id", "produto", "tipo", "quantidade", "data", "observacao", "acoes")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "movimentos-table"}
        row_attrs = {"data-id": lambda record: record.pk}
        order_by = ("-data",)

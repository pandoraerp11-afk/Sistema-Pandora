import django_tables2 as tables

from .models import ContaPagar, ContaReceber, Financeiro


class FinanceiroTable(tables.Table):
    """
    Tabela para exibição de movimentações financeiras com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # Adiciona coluna de ações com botões de editar e excluir
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'financeiro:financeiro_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'financeiro:financeiro_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # Personaliza a coluna de descrição para incluir um link para a página de detalhes
    descricao = tables.LinkColumn(
        "financeiro:financeiro_detail", args=[tables.A("pk")], attrs={"a": {"class": "financeiro-link"}}
    )

    # Personaliza a coluna de tipo para exibir um badge colorido
    tipo = tables.TemplateColumn(
        template_code="""
        {% if record.tipo == 'receita' %}
            <span class="badge bg-success">Receita</span>
        {% elif record.tipo == 'despesa' %}
            <span class="badge bg-danger">Despesa</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.tipo }}</span>
        {% endif %}
        """,
        verbose_name="Tipo",
    )

    # Personaliza a coluna de status para exibir um badge colorido
    status = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'pago' %}
            <span class="badge bg-success">Pago</span>
        {% elif record.status == 'recebido' %}
            <span class="badge bg-success">Recebido</span>
        {% elif record.status == 'pendente' %}
            <span class="badge bg-warning">Pendente</span>
        {% elif record.status == 'cancelado' %}
            <span class="badge bg-secondary">Cancelado</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status }}</span>
        {% endif %}
        """,
        verbose_name="Status",
    )

    # Personaliza a coluna de valor para exibir formatação monetária
    valor = tables.TemplateColumn(
        template_code="""
        {% if record.tipo == 'receita' %}
            <span class="text-success">R$ {{ record.valor|floatformat:2 }}</span>
        {% else %}
            <span class="text-danger">R$ {{ record.valor|floatformat:2 }}</span>
        {% endif %}
        """,
        verbose_name="Valor",
    )

    # Personaliza a coluna de obra
    obra = tables.Column(accessor="obra__nome", verbose_name="Obra", default="Não vinculado")

    class Meta:
        model = Financeiro
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id", "descricao", "tipo", "categoria", "data", "valor", "obra", "status", "acoes")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "financeiro-table"}
        row_attrs = {"data-id": lambda record: record.pk}
        order_by = ("-data",)  # Ordenação padrão


class ContaPagarTable(tables.Table):
    """
    Tabela para exibição de contas a pagar com suporte a ordenação, filtragem e paginação.
    """

    # Adiciona coluna de ações com botões de editar, excluir e marcar como pago
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'financeiro:conta_pagar_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'financeiro:conta_pagar_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
            {% if record.status != 'pago' %}
            <a href="{% url 'financeiro:conta_pagar_pagar' record.id %}" class="btn btn-sm btn-success">
                <i class="fas fa-check"></i>
            </a>
            {% endif %}
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # Personaliza a coluna de descrição para incluir um link para a página de detalhes
    descricao = tables.LinkColumn(
        "financeiro:conta_pagar_detail", args=[tables.A("pk")], attrs={"a": {"class": "conta-link"}}
    )

    # Personaliza a coluna de fornecedor
    fornecedor = tables.Column(accessor="fornecedor__nome", verbose_name="Fornecedor")

    # Personaliza a coluna de status para exibir um badge colorido
    status = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'pago' %}
            <span class="badge bg-success">Pago</span>
        {% elif record.status == 'pendente' %}
            <span class="badge bg-warning">Pendente</span>
        {% elif record.status == 'atrasado' %}
            <span class="badge bg-danger">Atrasado</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status }}</span>
        {% endif %}
        """,
        verbose_name="Status",
    )

    class Meta:
        model = ContaPagar
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id", "descricao", "fornecedor", "data_vencimento", "data_pagamento", "valor", "status")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "contas-pagar-table"}
        row_attrs = {
            "data-id": lambda record: record.pk,
            "class": lambda record: "table-danger" if record.status == "atrasado" else "",
        }
        order_by = ("-data_vencimento",)  # Ordenação padrão


class ContaReceberTable(tables.Table):
    """
    Tabela para exibição de contas a receber com suporte a ordenação, filtragem e paginação.
    """

    # Adiciona coluna de ações com botões de editar, excluir e marcar como recebido
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'financeiro:conta_receber_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'financeiro:conta_receber_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
            {% if record.status != 'recebido' %}
            <a href="{% url 'financeiro:conta_receber_receber' record.id %}" class="btn btn-sm btn-success">
                <i class="fas fa-check"></i>
            </a>
            {% endif %}
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # Personaliza a coluna de descrição para incluir um link para a página de detalhes
    descricao = tables.LinkColumn(
        "financeiro:conta_receber_detail", args=[tables.A("pk")], attrs={"a": {"class": "conta-link"}}
    )

    # Personaliza a coluna de cliente
    cliente = tables.Column(accessor="cliente__nome", verbose_name="Cliente")

    # Personaliza a coluna de status para exibir um badge colorido
    status = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'recebido' %}
            <span class="badge bg-success">Recebido</span>
        {% elif record.status == 'pendente' %}
            <span class="badge bg-warning">Pendente</span>
        {% elif record.status == 'atrasado' %}
            <span class="badge bg-danger">Atrasado</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status }}</span>
        {% endif %}
        """,
        verbose_name="Status",
    )

    class Meta:
        model = ContaReceber
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id", "descricao", "cliente", "data_vencimento", "data_recebimento", "valor", "status")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "contas-receber-table"}
        row_attrs = {
            "data-id": lambda record: record.pk,
            "class": lambda record: "table-danger" if record.status == "atrasado" else "",
        }
        order_by = ("-data_vencimento",)  # Ordenação padrão

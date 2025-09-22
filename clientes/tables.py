# clientes/tables.py (VERSÃO COM COLUNA TENANT)

import django_tables2 as tables
from django_tables2.utils import A  # Importando o Accessor 'A'

from .models import Cliente


class ClienteTable(tables.Table):
    """
    Tabela para exibição de clientes com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # --- NOVA COLUNA PARA O TENANT ---
    # Usando LinkColumn para que o nome da empresa seja um link para seus detalhes.
    tenant = tables.LinkColumn(
        "core:tenant_detail",  # view de destino: o detalhe do tenant
        # django-tables2 >= 2.7 recomenda '__' em vez de '.' para paths (deprecation warning)
        args=[A("tenant__pk")],  # argumento para a url: a pk do tenant do cliente
        text=lambda record: record.tenant.name,  # texto do link: o nome do tenant
        verbose_name="Empresa (Tenant)",
        order_by="tenant__name",
        attrs={"a": {"target": "_blank"}},  # Abre em nova aba para não sair da lista de clientes
    )
    # ------------------------------------

    # Coluna para o nome do cliente (pessoa física ou jurídica)
    nome = tables.Column(
        accessor="nome_display",
        verbose_name="Nome/Razão Social",
        order_by=("pessoafisica__nome_completo", "pessoajuridica__razao_social"),
    )

    # Coluna para o documento principal (CPF ou CNPJ)
    documento = tables.Column(
        accessor="documento_principal", verbose_name="CPF/CNPJ", order_by=("pessoafisica__cpf", "pessoajuridica__cnpj")
    )

    # Coluna para o tipo de cliente
    tipo_cliente = tables.Column(accessor="tipo", verbose_name="Tipo", order_by="tipo")

    # Personaliza a coluna de status para exibir um badge colorido
    status = tables.TemplateColumn(
        template_code="""
        {% if record.ativo %}
            <span class="badge bg-success">Ativo</span>
        {% else %}
            <span class="badge bg-danger">Inativo</span>
        {% endif %}
        """,
        verbose_name="Status",
        accessor="ativo",
    )

    # Adiciona coluna de ações com botões de visualizar, editar e excluir
    acoes = tables.TemplateColumn(
        template_name="clientes/partials/_clientes_actions_column.html",  # Usando um template externo para organização
        verbose_name="Ações",
        orderable=False,
    )

    class Meta:
        model = Cliente
        template_name = "django_tables2/bootstrap5.html"
        # ALTERAÇÃO: Adicionado 'tenant' na lista de campos a serem exibidos.
        fields = ("id", "nome", "tenant", "tipo_cliente", "documento", "email", "telefone", "status", "acoes")
        sequence = ("id", "nome", "tenant", "tipo_cliente", "documento", "email", "telefone", "status", "acoes")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "clientes-table"}
        row_attrs = {"data-id": lambda record: record.pk}

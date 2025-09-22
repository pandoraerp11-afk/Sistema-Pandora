# fornecedores/tables.py
import django_tables2 as tables

from .models import Fornecedor


class FornecedorTable(tables.Table):
    """
    Tabela para exibição de fornecedores com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # Coluna para o nome da empresa, que será um link para os detalhes
    # Como não existe 'nome_empresa' no modelo, vamos usar o __str__ do modelo
    nome_empresa = tables.LinkColumn(
        "fornecedores:fornecedor_detail",
        args=[tables.A("pk")],
        accessor="__str__",  # Usa o método __str__ do modelo
        verbose_name="Nome da Empresa",
        attrs={"a": {"class": "fornecedor-link"}},
    )

    # Email do primeiro contato
    email = tables.Column(accessor="contatos__email", verbose_name="E-mail", orderable=False)

    # Telefone do primeiro contato
    telefone = tables.Column(accessor="contatos__telefone", verbose_name="Telefone", orderable=False)

    # CNPJ para PJ ou CPF para PF
    cnpj = tables.TemplateColumn(
        template_code="""
        {% if record.tipo_pessoa == 'PJ' and record.pessoajuridica %}
            {{ record.pessoajuridica.cnpj }}
        {% elif record.tipo_pessoa == 'PF' and record.pessoafisica %}
            {{ record.pessoafisica.cpf }}
        {% else %}
            -
        {% endif %}
        """,
        verbose_name="CPF/CNPJ",
        orderable=False,
    )

    # Personaliza a coluna de categoria
    categoria = tables.TemplateColumn(
        template_code="""
        {% if record.categoria %}
            <span class="badge bg-info">{{ record.categoria.nome }}</span>
        {% else %}
            <span class="badge bg-secondary">Sem categoria</span>
        {% endif %}
        """,
        verbose_name="Categoria",
        accessor="categoria__nome",
    )

    # Personaliza a coluna de status
    status_ativo = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'active' %}
            <span class="badge bg-success">Ativo</span>
        {% elif record.status == 'inactive' %}
            <span class="badge bg-danger">Inativo</span>
        {% else %}
            <span class="badge bg-warning">Suspenso</span>
        {% endif %}
        """,
        verbose_name="Status",
        accessor="status",
    )

    # Adiciona coluna de ações com botões de editar e excluir
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'fornecedores:fornecedor_detail' record.pk %}" class="btn btn-sm btn-info" title="Ver detalhes">
                <i class="fas fa-eye"></i>
            </a>
            <a href="{% url 'fornecedores:fornecedor_wizard_edit' record.pk %}" class="btn btn-sm btn-warning" title="Editar">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'fornecedores:fornecedor_delete' record.pk %}" class="btn btn-sm btn-danger delete-btn" title="Excluir">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    class Meta:
        model = Fornecedor
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "id",
            "nome_empresa",
            "email",
            "telefone",
            "cnpj",
            "categoria",
            "status_ativo",
            "data_cadastro",
            "acoes",
        )
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "fornecedores-table"}
        row_attrs = {"data-id": lambda record: record.pk}
        order_by = ("id",)  # Ordenação padrão por ID já que nome_empresa não existe no modelo

import django_tables2 as tables

from .models import Obra


class ObraTable(tables.Table):
    """
    Tabela para exibição de obras com suporte a ordenação, filtragem e paginação.
    Implementa recursos avançados do django-tables2 para melhor experiência do usuário.
    """

    # Adiciona coluna de ações com botões de editar e excluir
    acoes = tables.TemplateColumn(
        template_code="""
        <div class="btn-group">
            <a href="{% url 'obras:obra_edit' record.id %}" class="btn btn-sm btn-info">
                <i class="fas fa-edit"></i>
            </a>
            <a href="{% url 'obras:obra_delete' record.id %}" class="btn btn-sm btn-danger delete-btn">
                <i class="fas fa-trash"></i>
            </a>
        </div>
        """,
        verbose_name="Ações",
        orderable=False,
    )

    # Personaliza a coluna de nome para incluir um link para a página de detalhes
    nome = tables.LinkColumn("obras:obra_detail", args=[tables.A("pk")], attrs={"a": {"class": "obra-link"}})

    # Personaliza a coluna de status para exibir um badge colorido
    status = tables.TemplateColumn(
        template_code="""
        {% if record.status == 'em_andamento' %}
            <span class="badge bg-primary">Em Andamento</span>
        {% elif record.status == 'concluida' %}
            <span class="badge bg-success">Concluída</span>
        {% elif record.status == 'paralisada' %}
            <span class="badge bg-warning">Paralisada</span>
        {% elif record.status == 'cancelada' %}
            <span class="badge bg-danger">Cancelada</span>
        {% else %}
            <span class="badge bg-secondary">{{ record.status }}</span>
        {% endif %}
        """,
        verbose_name="Status",
    )

    # Personaliza a coluna de cliente para exibir o nome do cliente
    # Substituição de accessor com ponto por notação '__' recomendada (compatibilidade futura django_tables2)
    cliente = tables.Column(accessor="cliente__nome", verbose_name="Cliente")

    # Personaliza a coluna de progresso para exibir uma barra de progresso
    progresso = tables.TemplateColumn(
        template_code="""
        <div class="progress">
            <div class="progress-bar bg-success" role="progressbar" style="width: {{ record.progresso }}%;" 
                 aria-valuenow="{{ record.progresso }}" aria-valuemin="0" aria-valuemax="100">
                {{ record.progresso }}%
            </div>
        </div>
        """,
        verbose_name="Progresso",
    )

    class Meta:
        model = Obra
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id", "nome", "cliente", "data_inicio", "data_previsao_termino", "status", "progresso", "valor_total")
        attrs = {"class": "table table-striped table-hover table-bordered", "id": "obras-table"}
        row_attrs = {"data-id": lambda record: record.pk}
        order_by = ("-data_inicio",)  # Ordenação padrão

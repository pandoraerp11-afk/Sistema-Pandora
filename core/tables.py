# core/tables.py (VERSÃO FINAL E AUDITADA)

import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from .models import Tenant


class TenantTable(tables.Table):
    """
    Tabela para listar as Empresas (Tenants).
    Esta versão está atualizada para mostrar os campos do modelo expandido do Tenant,
    garantindo uma visualização completa e profissional.
    """

    # Exibe o "Nome Fantasia" (ou Nome Completo para PF)
    name = tables.Column(verbose_name=_("Nome Fantasia / Nome"))

    # Exibe a Razão Social, que só será preenchida para PJ
    razao_social = tables.Column(verbose_name=_("Razão Social"), empty_values=(), orderable=False)

    # Coluna de ações customizada (do seu código original)
    actions = tables.TemplateColumn(
        template_name="core/partials/tenant_actions_column.html",
        verbose_name=_("Ações"),
        orderable=False,
        attrs={"td": {"class": "text-right"}},
    )

    class Meta:
        model = Tenant
        template_name = "django_tables2/bootstrap5.html"
        # Campos a serem exibidos na tabela.
        # Mantém os campos originais e adiciona o 'cpf' para visualização completa.
        fields = ("name", "razao_social", "cnpj", "cpf", "subdomain", "status", "actions")
        sequence = ("name", "razao_social", "cnpj", "cpf", "subdomain", "status", "actions")
        attrs = {"class": "table table-bordered table-striped table-hover", "id": "tenant_table"}

    def render_razao_social(self, value, record):
        # Mostra a razão social apenas se for Pessoa Jurídica
        return record.razao_social if record.tipo_pessoa == "PJ" and record.razao_social else "—"

    def render_cnpj(self, value, record):
        # Mostra o CNPJ apenas se for Pessoa Jurídica
        return value if record.tipo_pessoa == "PJ" else "—"

    def render_cpf(self, value, record):
        # Mostra o CPF apenas se for Pessoa Física
        return value if record.tipo_pessoa == "PF" else "—"

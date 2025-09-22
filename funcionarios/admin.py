# funcionarios/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Beneficio,
    CartaoPonto,
    DecimoTerceiro,
    Dependente,
    Ferias,
    Folga,
    Funcionario,
    HorarioTrabalho,
    SalarioHistorico,
)


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["nome_completo", "cpf", "cargo", "departamento", "data_admissao", "ativo", "tenant"]
    list_filter = ["ativo", "tipo_contrato", "departamento", "sexo", "estado_civil", "tenant", "data_admissao"]
    search_fields = ["nome_completo", "cpf", "cargo", "email_pessoal"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            _("Informações Básicas"),
            {
                "fields": (
                    "tenant",
                    "user",
                    "nome_completo",
                    "cpf",
                    "rg",
                    "data_nascimento",
                    "sexo",
                    "estado_civil",
                    "nacionalidade",
                    "escolaridade",
                )
            },
        ),
        (_("Contato"), {"fields": ("email_pessoal", "telefone_pessoal", "telefone_emergencia", "contato_emergencia")}),
        (
            _("Endereço"),
            {
                "fields": (
                    "endereco_logradouro",
                    "endereco_numero",
                    "endereco_complemento",
                    "endereco_bairro",
                    "endereco_cidade",
                    "endereco_uf",
                    "endereco_cep",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Informações Trabalhistas"),
            {
                "fields": (
                    "data_admissao",
                    "data_demissao",
                    "ativo",
                    "cargo",
                    "departamento",
                    "tipo_contrato",
                    "jornada_trabalho_horas",
                )
            },
        ),
        (_("Informações Salariais"), {"fields": ("salario_base",)}),
        (_("Informações Bancárias"), {"fields": ("banco", "agencia", "conta", "tipo_conta"), "classes": ("collapse",)}),
        (
            _("Documentos Trabalhistas"),
            {"fields": ("pis", "ctps", "titulo_eleitor", "reservista"), "classes": ("collapse",)},
        ),
        (_("Outros"), {"fields": ("numero_dependentes", "observacoes"), "classes": ("collapse",)}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


class DependenteInline(admin.TabularInline):
    model = Dependente
    extra = 0
    fields = [
        "nome_completo",
        "cpf",
        "data_nascimento",
        "tipo_dependente",
        "dependente_ir",
        "dependente_salario_familia",
    ]


class HorarioTrabalhoInline(admin.TabularInline):
    model = HorarioTrabalho
    extra = 0
    fields = ["dia_semana", "hora_entrada", "hora_saida", "hora_inicio_almoco", "hora_fim_almoco", "ativo"]


@admin.register(Ferias)
class FeriasAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "data_inicio", "data_fim", "dias_gozados", "status", "tenant"]
    list_filter = ["status", "abono_pecuniario", "tenant", "data_inicio"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "status")}),
        (_("Período Aquisitivo"), {"fields": ("periodo_aquisitivo_inicio", "periodo_aquisitivo_fim")}),
        (_("Período de Férias"), {"fields": ("data_inicio", "data_fim", "dias_gozados")}),
        (_("Abono Pecuniário"), {"fields": ("abono_pecuniario", "dias_abono")}),
        (_("Pagamento"), {"fields": ("data_pagamento", "valor_pago")}),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(DecimoTerceiro)
class DecimoTerceiroAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "ano_referencia", "tipo_parcela", "valor_bruto", "valor_liquido", "status", "tenant"]
    list_filter = ["ano_referencia", "tipo_parcela", "status", "tenant"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf"]
    readonly_fields = ["created_at", "updated_at", "valor_liquido", "total_descontos"]

    fieldsets = (
        (
            _("Informações Básicas"),
            {"fields": ("tenant", "funcionario", "ano_referencia", "tipo_parcela", "meses_trabalhados")},
        ),
        (
            _("Valores"),
            {"fields": ("valor_bruto", "desconto_inss", "desconto_irrf", "outros_descontos", "valor_liquido")},
        ),
        (_("Pagamento"), {"fields": ("data_pagamento", "status")}),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(Folga)
class FolgaAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "data_inicio", "data_fim", "tipo_folga", "status", "aprovado_por", "tenant"]
    list_filter = ["tipo_folga", "status", "tenant", "data_inicio"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf", "motivo"]
    readonly_fields = ["created_at", "updated_at", "dias_folga"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "tipo_folga")}),
        (_("Período"), {"fields": ("data_inicio", "data_fim", "dias_folga")}),
        (_("Detalhes"), {"fields": ("motivo", "documento_comprobatorio")}),
        (_("Aprovação"), {"fields": ("status", "aprovado_por", "data_aprovacao", "observacoes_aprovacao")}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(CartaoPonto)
class CartaoPontoAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "data_hora_registro", "tipo_registro", "aprovado", "tenant"]
    list_filter = ["tipo_registro", "aprovado", "tenant", "data_hora_registro"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "data_hora_registro", "tipo_registro")}),
        (_("Localização"), {"fields": ("ip_origem", "localizacao")}),
        (_("Aprovação"), {"fields": ("aprovado", "aprovado_por", "justificativa")}),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(Beneficio)
class BeneficioAdmin(admin.ModelAdmin):
    list_display = [
        "funcionario",
        "tipo_beneficio",
        "categoria",
        "valor",
        "data_referencia",
        "recorrente",
        "ativo",
        "tenant",
    ]
    list_filter = ["tipo_beneficio", "categoria", "recorrente", "ativo", "tenant", "data_referencia"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "tipo_beneficio", "categoria")}),
        (_("Valores e Datas"), {"fields": ("valor", "data_referencia")}),
        (_("Configurações"), {"fields": ("recorrente", "ativo")}),
        (_("Observações"), {"fields": ("observacoes",)}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(SalarioHistorico)
class SalarioHistoricoAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "data_vigencia", "valor_salario", "motivo_alteracao", "alterado_por", "tenant"]
    list_filter = ["tenant", "data_vigencia"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf", "motivo_alteracao"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "data_vigencia", "valor_salario")}),
        (_("Alteração"), {"fields": ("motivo_alteracao", "alterado_por")}),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(Dependente)
class DependenteAdmin(admin.ModelAdmin):
    list_display = ["nome_completo", "funcionario", "tipo_dependente", "data_nascimento", "dependente_ir", "tenant"]
    list_filter = ["tipo_dependente", "dependente_ir", "dependente_salario_familia", "tenant"]
    search_fields = ["nome_completo", "cpf", "funcionario__nome_completo"]
    readonly_fields = ["created_at", "updated_at", "idade"]

    fieldsets = (
        (
            _("Informações Básicas"),
            {"fields": ("tenant", "funcionario", "nome_completo", "cpf", "data_nascimento", "tipo_dependente")},
        ),
        (_("Configurações"), {"fields": ("dependente_ir", "dependente_salario_familia")}),
        (_("Metadados"), {"fields": ("created_at", "updated_at", "idade"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs


@admin.register(HorarioTrabalho)
class HorarioTrabalhoAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "dia_semana", "hora_entrada", "hora_saida", "ativo", "tenant"]
    list_filter = ["dia_semana", "ativo", "tenant"]
    search_fields = ["funcionario__nome_completo", "funcionario__cpf"]
    readonly_fields = ["created_at", "updated_at", "horas_trabalhadas"]

    fieldsets = (
        (_("Informações Básicas"), {"fields": ("tenant", "funcionario", "dia_semana", "ativo")}),
        (
            _("Horários"),
            {"fields": ("hora_entrada", "hora_saida", "hora_inicio_almoco", "hora_fim_almoco", "horas_trabalhadas")},
        ),
        (_("Metadados"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, "tenant_memberships"):
            tenant_ids = request.user.tenant_memberships.values_list("tenant_id", flat=True)
            return qs.filter(tenant_id__in=tenant_ids)
        return qs

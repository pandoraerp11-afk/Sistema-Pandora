from django.contrib import admin

from .models import (
    Anamnese,
    Atendimento,
    FotoEvolucao,
    PerfilClinico,
)

"""Admin refatorado: modelo Paciente removido.
Campos renomeados: satisfacao_paciente->satisfacao_cliente, assinatura_paciente->assinatura_cliente,
visivel_paciente->visivel_cliente."""

## Admin de Procedimento removido (migrado para Servico/ServicoClinico)


@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "servico", "profissional", "data_atendimento", "status", "valor_cobrado", "tenant")
    search_fields = (
        "cliente__nome_razao_social",
        "servico__nome",
        "profissional__first_name",
        "profissional__last_name",
    )
    list_filter = ("status", "profissional", "tenant")
    date_hierarchy = "data_atendimento"
    fieldsets = (
        (
            None,
            {"fields": ("tenant", "cliente", "servico", "profissional", "data_atendimento", "numero_sessao", "status")},
        ),
        ("Avaliação Pré-Serviço", {"fields": ("pressao_arterial", "peso", "altura", "observacoes_pre_procedimento")}),
        (
            "Detalhes do Serviço",
            {
                "fields": (
                    "area_tratada",
                    "equipamento_utilizado",
                    "parametros_equipamento",
                    "produtos_utilizados",
                    "observacoes_durante_procedimento",
                )
            },
        ),
        ("Pós-Serviço e Reações", {"fields": ("observacoes_pos_procedimento", "reacoes_adversas")}),
        ("Avaliação de Resultados", {"fields": ("satisfacao_cliente", "avaliacao_profissional")}),
        ("Financeiro", {"fields": ("valor_cobrado", "desconto_aplicado", "forma_pagamento")}),
        ("Próxima Sessão", {"fields": ("data_proxima_sessao", "observacoes_proxima_sessao")}),
        ("Assinaturas", {"fields": ("assinatura_cliente", "assinatura_profissional")}),
    )
    raw_id_fields = ("tenant", "cliente", "servico", "profissional")


@admin.register(FotoEvolucao)
class FotoEvolucaoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "titulo", "tipo_foto", "momento", "data_foto", "tenant")
    search_fields = ("cliente__nome_razao_social", "titulo", "area_fotografada")
    list_filter = ("tipo_foto", "momento", "visivel_cliente", "tenant")
    date_hierarchy = "data_foto"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "tenant",
                    "cliente",
                    "atendimento",
                    "titulo",
                    "tipo_foto",
                    "momento",
                    "area_fotografada",
                    "imagem",
                    "imagem_thumbnail",
                    "data_foto",
                    "observacoes",
                )
            },
        ),
        (
            "Metadados da Foto",
            {"fields": ("angulo_foto", "iluminacao", "resolucao", "tamanho_arquivo", "hash_arquivo")},
        ),
        ("Privacidade", {"fields": ("visivel_cliente", "uso_autorizado_marketing")}),
    )
    raw_id_fields = ("tenant", "cliente", "atendimento")


@admin.register(Anamnese)
class AnamneseAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "servico",
        "tipo_anamnese",
        "status",
        "data_preenchimento",
        "profissional_responsavel",
        "tenant",
    )
    search_fields = (
        "cliente__nome_razao_social",
        "servico__nome",
        "profissional_responsavel__first_name",
        "profissional_responsavel__last_name",
    )
    list_filter = ("tipo_anamnese", "status", "profissional_responsavel", "tenant")
    date_hierarchy = "data_preenchimento"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "tenant",
                    "cliente",
                    "servico",
                    "atendimento",
                    "tipo_anamnese",
                    "profissional_responsavel",
                    "respostas",
                    "observacoes_profissional",
                    "contraindicacoes_identificadas",
                    "recomendacoes",
                    "status",
                )
            },
        ),
        ("Aprovação", {"fields": ("aprovada_por", "data_aprovacao")}),
        ("Assinaturas", {"fields": ("assinatura_cliente", "assinatura_profissional")}),
    )
    raw_id_fields = ("tenant", "cliente", "servico", "atendimento", "profissional_responsavel", "aprovada_por")


"""Admin de Disponibilidade/Slot removido deste módulo (centralização na Agenda)."""


@admin.register(PerfilClinico)
class PerfilClinicoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "tipo_sanguineo", "fototipo", "ativo", "tenant")
    search_fields = (
        "cliente__nome_razao_social",
        "cliente__documento_principal",
        "pessoa_fisica__nome_completo",
        "pessoa_fisica__cpf",
    )
    list_filter = ("ativo", "tipo_sanguineo", "fototipo", "lgpd_consentimento", "tenant")
    fieldsets = (
        (None, {"fields": ("tenant", "cliente", "pessoa_fisica", "ativo")}),
        (
            "Dados Médicos",
            {"fields": ("tipo_sanguineo", "alergias", "medicamentos_uso", "doencas_cronicas", "cirurgias_anteriores")},
        ),
        ("Dados Estéticos", {"fields": ("tipo_pele", "fototipo", "historico_estetico")}),
        (
            "Contato de Emergência",
            {"fields": ("contato_emergencia_nome", "contato_emergencia_telefone", "contato_emergencia_parentesco")},
        ),
        (
            "Consentimentos",
            {
                "fields": (
                    "termo_responsabilidade_assinado",
                    "data_assinatura_termo",
                    "lgpd_consentimento",
                    "data_consentimento_lgpd",
                )
            },
        ),
        ("Observações", {"fields": ("observacoes_gerais",)}),
    )
    raw_id_fields = ("tenant", "cliente", "pessoa_fisica")
    autocomplete_fields = ("cliente", "pessoa_fisica")
    ordering = ("cliente",)

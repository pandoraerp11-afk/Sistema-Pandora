from django.contrib import admin

from .models import ConfiguracaoAssistente, ConversaAssistente, MemoriaAssistente, MensagemAssistente, SkillExecution


@admin.register(ConversaAssistente)
class ConversaAssistenteAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "titulo", "data_inicio", "ativa", "modo_entrada"]
    list_filter = ["ativa", "modo_entrada", "data_inicio"]
    search_fields = ["usuario__username", "titulo"]
    readonly_fields = ["data_inicio", "data_fim"]
    ordering = ["-data_inicio"]


@admin.register(MensagemAssistente)
class MensagemAssistenteAdmin(admin.ModelAdmin):
    list_display = ["id", "conversa", "tipo", "conteudo_resumido", "intencao", "timestamp"]
    list_filter = ["tipo", "intencao", "timestamp"]
    search_fields = ["conteudo", "intencao"]
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def conteudo_resumido(self, obj):
        return obj.conteudo[:50] + "..." if len(obj.conteudo) > 50 else obj.conteudo

    conteudo_resumido.short_description = "Conteúdo"


@admin.register(MemoriaAssistente)
class MemoriaAssistenteAdmin(admin.ModelAdmin):
    list_display = ["usuario", "chave", "valor_resumido", "fonte", "data_criacao", "ativo"]
    list_filter = ["fonte", "ativo", "data_criacao"]
    search_fields = ["usuario__username", "chave", "valor"]
    readonly_fields = ["data_criacao", "data_atualizacao"]
    ordering = ["-data_atualizacao"]

    def valor_resumido(self, obj):
        return obj.valor[:30] + "..." if len(obj.valor) > 30 else obj.valor

    valor_resumido.short_description = "Valor"


@admin.register(SkillExecution)
class SkillExecutionAdmin(admin.ModelAdmin):
    list_display = ["conversa", "skill_name", "sucesso", "timestamp", "tempo_execucao"]
    list_filter = ["skill_name", "sucesso", "timestamp"]
    search_fields = ["skill_name", "resultado"]
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]


@admin.register(ConfiguracaoAssistente)
class ConfiguracaoAssistenteAdmin(admin.ModelAdmin):
    list_display = ["usuario", "modo_preferido", "auto_speak", "skills_count"]
    list_filter = ["modo_preferido", "auto_speak"]
    search_fields = ["usuario__username"]

    def skills_count(self, obj):
        return len(obj.skills_habilitadas) if obj.skills_habilitadas else 0

    skills_count.short_description = "Skills Habilitadas"

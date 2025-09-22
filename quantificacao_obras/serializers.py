from rest_framework import serializers

from .models import AnexoQuantificacao, ItemQuantificacao, ProjetoQuantificacao


class AnexoQuantificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnexoQuantificacao
        fields = [
            "id",
            "nome_arquivo",
            "arquivo",
            "tipo_arquivo",
            "tamanho_arquivo",
            "upload_por",
            "observacoes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["upload_por", "tamanho_arquivo", "created_at", "updated_at"]


class ItemQuantificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemQuantificacao
        fields = [
            "id",
            "nome",
            "unidade_medida",
            "quantidade",
            "custo_unitario",
            "custo_total",
            "observacoes",
            "tipo_item",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["custo_total", "created_at", "updated_at"]


class ProjetoQuantificacaoSerializer(serializers.ModelSerializer):
    itens_quantificacao = ItemQuantificacaoSerializer(many=True, read_only=True)
    anexos_quantificacao = AnexoQuantificacaoSerializer(many=True, read_only=True)

    class Meta:
        model = ProjetoQuantificacao
        fields = [
            "id",
            "nome",
            "descricao",
            "data_inicio",
            "data_previsao_conclusao",
            "status",
            "responsavel",
            "tenant",
            "itens_quantificacao",
            "anexos_quantificacao",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["responsavel", "tenant", "created_at", "updated_at"]

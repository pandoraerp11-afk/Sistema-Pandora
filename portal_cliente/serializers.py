from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ContaCliente, DocumentoPortalCliente

User = get_user_model()


class ContaClienteSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source="usuario.get_full_name", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    pode_acessar = serializers.BooleanField(source="pode_acessar_portal", read_only=True)

    class Meta:
        model = ContaCliente
        fields = [
            "id",
            "cliente",
            "cliente_nome",
            "usuario",
            "usuario_nome",
            "ativo",
            "is_admin_portal",
            "data_concessao",
            "data_ultimo_acesso",
            "pode_acessar",
            "observacoes",
        ]
        read_only_fields = ["id", "data_concessao", "data_ultimo_acesso"]


class DocumentoPortalClienteSerializer(serializers.ModelSerializer):
    documento_tipo = serializers.CharField(source="documento_versao.documento.tipo.nome", read_only=True)
    documento_status = serializers.CharField(source="documento_versao.status", read_only=True)
    arquivo_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoPortalCliente
        fields = [
            "id",
            "conta",
            "documento_versao",
            "documento_tipo",
            "documento_status",
            "titulo_externo",
            "descricao_externa",
            "arquivo_url",
            "expiracao_visualizacao",
            "ativo",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "arquivo_url"]

    def get_arquivo_url(self, obj):
        req = self.context.get("request")
        if obj.esta_visivel() and obj.documento_versao.arquivo:
            url = obj.documento_versao.arquivo.url
            if req:
                return req.build_absolute_uri(url)
            return url
        return None

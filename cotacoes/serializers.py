"""
Serializers para cotações e portal fornecedor.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from portal_fornecedor.models import AcessoFornecedor

from .models import Cotacao, CotacaoItem, PropostaFornecedor, PropostaFornecedorItem

User = get_user_model()


class CotacaoItemSerializer(serializers.ModelSerializer):
    """Serializer para itens da cotação."""

    produto_nome = serializers.CharField(source="produto.nome", read_only=True)
    total_quantidade = serializers.SerializerMethodField()

    class Meta:
        model = CotacaoItem
        fields = [
            "id",
            "produto",
            "produto_nome",
            "descricao",
            "especificacao",
            "quantidade",
            "unidade",
            "ordem",
            "total_quantidade",
        ]
        read_only_fields = ["id"]

    def get_total_quantidade(self, obj):
        """Retorna quantidade formatada com unidade."""
        return f"{obj.quantidade} {obj.unidade}"


class CotacaoListSerializer(serializers.ModelSerializer):
    """Serializer para listagem de cotações."""

    criado_por_nome = serializers.CharField(source="criado_por.get_full_name", read_only=True)
    total_itens = serializers.SerializerMethodField()
    total_propostas = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_aberta = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cotacao
        fields = [
            "id",
            "codigo",
            "titulo",
            "status",
            "status_display",
            "data_abertura",
            "prazo_proposta",
            "valor_estimado",
            "criado_por_nome",
            "total_itens",
            "total_propostas",
            "is_aberta",
        ]

    def get_total_itens(self, obj):
        return obj.itens.count()

    def get_total_propostas(self, obj):
        return obj.propostas.count()


class CotacaoDetailSerializer(serializers.ModelSerializer):
    """Serializer detalhado para cotação."""

    itens = CotacaoItemSerializer(many=True, read_only=True)
    criado_por_nome = serializers.CharField(source="criado_por.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_aberta = serializers.BooleanField(read_only=True)
    total_propostas = serializers.SerializerMethodField()
    propostas_enviadas = serializers.SerializerMethodField()

    class Meta:
        model = Cotacao
        fields = [
            "id",
            "codigo",
            "titulo",
            "descricao",
            "status",
            "status_display",
            "data_abertura",
            "prazo_proposta",
            "data_encerramento",
            "valor_estimado",
            "criado_por_nome",
            "is_aberta",
            "total_propostas",
            "propostas_enviadas",
            "itens",
            "created_at",
        ]

    def get_total_propostas(self, obj):
        return obj.propostas.count()

    def get_propostas_enviadas(self, obj):
        return obj.propostas.filter(status="enviada").count()


class CotacaoCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de cotação."""

    itens = CotacaoItemSerializer(many=True, write_only=True)

    class Meta:
        model = Cotacao
        fields = ["codigo", "titulo", "descricao", "prazo_proposta", "valor_estimado", "observacoes_internas", "itens"]

    def validate_prazo_proposta(self, value):
        """Valida se prazo é futuro."""
        from django.utils import timezone

        if value <= timezone.now():
            raise serializers.ValidationError("Prazo deve ser futuro")
        return value

    def validate_itens(self, value):
        """Valida se há pelo menos um item."""
        if not value:
            raise serializers.ValidationError("Deve haver pelo menos um item")
        return value

    def create(self, validated_data):
        """Cria cotação com itens."""
        from core.utils import get_current_tenant

        from .services.cotacao_service import CotacaoService

        itens_data = validated_data.pop("itens")
        request = self.context["request"]
        tenant = get_current_tenant(request)

        cotacao = CotacaoService.criar_cotacao(
            tenant=tenant, criado_por=request.user, itens=itens_data, **validated_data
        )

        return cotacao


class PropostaFornecedorItemSerializer(serializers.ModelSerializer):
    """Serializer para itens da proposta."""

    item_cotacao_descricao = serializers.CharField(source="item_cotacao.descricao", read_only=True)
    item_cotacao_quantidade = serializers.DecimalField(
        source="item_cotacao.quantidade", max_digits=10, decimal_places=3, read_only=True
    )
    item_cotacao_unidade = serializers.CharField(source="item_cotacao.unidade", read_only=True)
    total_item = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = PropostaFornecedorItem
        fields = [
            "id",
            "item_cotacao",
            "item_cotacao_descricao",
            "item_cotacao_quantidade",
            "item_cotacao_unidade",
            "preco_unitario",
            "prazo_entrega_dias",
            "total_item",
            "observacao_item",
            "disponibilidade",
        ]
        read_only_fields = ["id", "item_cotacao"]


class PropostaFornecedorListSerializer(serializers.ModelSerializer):
    """Serializer para listagem de propostas."""

    cotacao_codigo = serializers.CharField(source="cotacao.codigo", read_only=True)
    cotacao_titulo = serializers.CharField(source="cotacao.titulo", read_only=True)
    fornecedor_nome = serializers.CharField(source="fornecedor.nome_fantasia", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    pode_editar = serializers.BooleanField(read_only=True)

    class Meta:
        model = PropostaFornecedor
        fields = [
            "id",
            "cotacao",
            "cotacao_codigo",
            "cotacao_titulo",
            "fornecedor_nome",
            "status",
            "status_display",
            "total_estimado",
            "enviado_em",
            "validade_proposta",
            "pode_editar",
            "created_at",
        ]


class PropostaFornecedorDetailSerializer(serializers.ModelSerializer):
    """Serializer detalhado para proposta."""

    itens = PropostaFornecedorItemSerializer(many=True, read_only=True)
    cotacao = CotacaoDetailSerializer(read_only=True)
    fornecedor_nome = serializers.CharField(source="fornecedor.nome_fantasia", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    pode_editar = serializers.BooleanField(read_only=True)
    usuario_nome = serializers.CharField(source="usuario.get_full_name", read_only=True)

    class Meta:
        model = PropostaFornecedor
        fields = [
            "id",
            "cotacao",
            "fornecedor_nome",
            "usuario_nome",
            "status",
            "status_display",
            "enviado_em",
            "total_estimado",
            "validade_proposta",
            "prazo_entrega_geral",
            "condicoes_pagamento",
            "observacao",
            "pode_editar",
            "itens",
            "created_at",
            "updated_at",
        ]


class PropostaFornecedorCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de proposta."""

    class Meta:
        model = PropostaFornecedor
        fields = ["cotacao", "validade_proposta", "prazo_entrega_geral", "condicoes_pagamento", "observacao"]

    def validate_validade_proposta(self, value):
        """Valida se validade é futura."""
        from django.utils import timezone

        if value <= timezone.now().date():
            raise serializers.ValidationError("Validade deve ser futura")
        return value

    def validate_cotacao(self, value):
        """Valida se pode criar proposta para esta cotação."""
        request = self.context["request"]

        # Buscar fornecedor do usuário
        try:
            acesso = AcessoFornecedor.objects.get(usuario=request.user, ativo=True)
            fornecedor = acesso.fornecedor
        except AcessoFornecedor.DoesNotExist:
            raise serializers.ValidationError("Usuário não tem acesso de fornecedor")

        # Verificar se pode participar
        pode, motivo = value.pode_receber_proposta(fornecedor)
        if not pode:
            raise serializers.ValidationError(motivo)

        return value

    def create(self, validated_data):
        """Cria proposta."""
        from .services.cotacao_service import PropostaService

        request = self.context["request"]
        acesso = AcessoFornecedor.objects.get(usuario=request.user, ativo=True)

        proposta = PropostaService.criar_proposta(fornecedor=acesso.fornecedor, usuario=request.user, **validated_data)

        return proposta


class PropostaItemUpdateSerializer(serializers.ModelSerializer):
    """Serializer para atualização de item da proposta."""

    class Meta:
        model = PropostaFornecedorItem
        fields = ["preco_unitario", "prazo_entrega_dias", "observacao_item", "disponibilidade"]

    def validate_preco_unitario(self, value):
        """Valida se preço é positivo."""
        if value <= 0:
            raise serializers.ValidationError("Preço deve ser positivo")
        return value

    def validate_prazo_entrega_dias(self, value):
        """Valida se prazo é positivo."""
        if value <= 0:
            raise serializers.ValidationError("Prazo deve ser positivo")
        return value

    def update(self, instance, validated_data):
        """Atualiza item usando service."""
        from .services.cotacao_service import PropostaService

        return PropostaService.atualizar_item_proposta(
            proposta=instance.proposta, item_cotacao_id=instance.item_cotacao.id, **validated_data
        )


class AcessoFornecedorSerializer(serializers.ModelSerializer):
    """Serializer para acesso de fornecedor."""

    usuario_nome = serializers.CharField(source="usuario.get_full_name", read_only=True)
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)
    fornecedor_nome = serializers.CharField(source="fornecedor.nome_fantasia", read_only=True)
    pode_acessar = serializers.BooleanField(source="pode_acessar_portal", read_only=True)

    class Meta:
        model = AcessoFornecedor
        fields = [
            "id",
            "usuario",
            "usuario_nome",
            "usuario_email",
            "fornecedor_nome",
            "is_admin_portal",
            "ativo",
            "data_concessao",
            "data_ultimo_acesso",
            "pode_acessar",
            "observacoes",
        ]
        read_only_fields = ["id", "data_concessao", "data_ultimo_acesso"]

"""
Serializers para API de Reservas de Estoque
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from estoque.models import EstoqueSaldo, ReservaEstoque


class ReservaEstoqueSerializer(serializers.ModelSerializer):
    """Serializer completo para visualização de reservas"""

    produto_nome = serializers.CharField(source="produto.nome", read_only=True)
    produto_sku = serializers.CharField(source="produto.sku", read_only=True)
    deposito_nome = serializers.CharField(source="deposito.nome", read_only=True)
    criado_por_nome = serializers.CharField(source="criado_por.get_full_name", read_only=True)

    class Meta:
        model = ReservaEstoque
        fields = [
            "id",
            "produto",
            "produto_nome",
            "produto_sku",
            "deposito",
            "deposito_nome",
            "quantidade",
            "status",
            "origem_tipo",
            "origem_id",
            "motivo",
            "observacoes",
            "criado_em",
            "expira_em",
            "consumida_em",
            "cancelada_em",
            "criado_por",
            "criado_por_nome",
        ]
        read_only_fields = ["id", "criado_em", "consumida_em", "cancelada_em", "criado_por"]


class ReservaEstoqueCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de reservas com validações"""

    expira_em = serializers.DateTimeField(required=False)

    class Meta:
        model = ReservaEstoque
        fields = ["produto", "deposito", "quantidade", "origem_tipo", "origem_id", "motivo", "observacoes", "expira_em"]

    def validate_quantidade(self, value):
        """Validar quantidade positiva"""
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero")
        return value

    def validate_expira_em(self, value):
        """Validar data de expiração"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Data de expiração deve ser futura")
        return value

    def validate(self, attrs):
        """Validações de negócio"""
        produto = attrs.get("produto")
        deposito = attrs.get("deposito")
        quantidade = attrs.get("quantidade")

        # Verificar se produto existe no depósito
        try:
            saldo = EstoqueSaldo.objects.get(produto=produto, deposito=deposito)
        except EstoqueSaldo.DoesNotExist:
            raise serializers.ValidationError("Produto não possui saldo neste depósito")

        # Verificar disponibilidade
        if saldo.disponivel < quantidade:
            raise serializers.ValidationError(f"Saldo insuficiente. Disponível: {saldo.disponivel}")

        # Se não informou expiração, usar padrão de 7 dias
        if not attrs.get("expira_em"):
            attrs["expira_em"] = timezone.now() + timedelta(days=7)

        return attrs


class ReservaEstoqueUpdateSerializer(serializers.ModelSerializer):
    """Serializer para atualização de reservas"""

    class Meta:
        model = ReservaEstoque
        fields = ["quantidade", "expira_em", "motivo", "observacoes"]

    def validate_quantidade(self, value):
        """Validar quantidade positiva"""
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero")
        return value

    def validate_expira_em(self, value):
        """Validar data de expiração"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Data de expiração deve ser futura")
        return value


class ConsumoReservaSerializer(serializers.Serializer):
    """Serializer para consumir reserva"""

    quantidade = serializers.DecimalField(max_digits=15, decimal_places=4)
    motivo = serializers.CharField(max_length=500, required=False, default="Consumo de reserva")

    def validate_quantidade(self, value):
        """Validar quantidade positiva"""
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero")
        return value

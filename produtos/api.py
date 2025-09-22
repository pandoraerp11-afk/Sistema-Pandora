from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Produto, ProdutoAtributoDef, ProdutoAtributoValor, ProdutoBOMItem


class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = "__all__"  # inclui novos campos


class ProdutoAtributoDefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdutoAtributoDef
        fields = ["id", "nome", "tipo", "unidade_id", "obrigatorio", "ativo", "criado_em", "atualizado_em"]
        read_only_fields = ["criado_em", "atualizado_em"]


class ProdutoAtributoValorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdutoAtributoValor
        fields = [
            "id",
            "produto_id",
            "atributo_def_id",
            "valor_textual",
            "valor_num",
            "valor_json",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["criado_em", "atualizado_em"]


class ProdutoBOMItemSerializer(serializers.ModelSerializer):
    componente_nome = serializers.CharField(source="componente.nome", read_only=True)

    class Meta:
        model = ProdutoBOMItem
        fields = [
            "id",
            "produto_pai_id",
            "componente_id",
            "componente_nome",
            "quantidade_por_unidade",
            "perda_perc",
            "ativo",
            "criado_em",
        ]
        read_only_fields = ["criado_em"]


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
    filterset_fields = ["sku", "categoria_id", "tipo", "status_ciclo", "ativo"]

    @action(detail=True, methods=["get"])
    def resumo(self, request, pk=None):
        from estoque.models import EstoqueSaldo, MovimentoEstoque, ReservaEstoque

        produto = self.get_object()
        saldos = list(
            EstoqueSaldo.objects.filter(produto=produto).values("deposito_id", "quantidade", "reservado", "custo_medio")
        )
        reservas = list(
            ReservaEstoque.objects.filter(produto=produto, status="ATIVA").values(
                "deposito_id", "quantidade", "origem_tipo"
            )
        )
        custo_medio_global = 0
        if saldos:
            total_valor = sum(float(s["quantidade"]) * float(s["custo_medio"]) for s in saldos)
            total_qtd = sum(float(s["quantidade"]) for s in saldos)
            custo_medio_global = (total_valor / total_qtd) if total_qtd else 0
        cutoff = timezone.now() - timedelta(days=30)
        rupturas_30d = MovimentoEstoque.objects.filter(
            produto=produto, tipo="SAIDA", criado_em__gte=cutoff
        ).count() == 0 and any(
            float(s["quantidade"]) <= 0 or float(s["quantidade"]) <= float(s["reservado"]) for s in saldos
        )
        atributos = list(
            produto.atributos_valores.select_related("atributo_def").values(
                "atributo_def__nome", "valor_textual", "valor_num", "valor_json"
            )
        )
        return Response(
            {
                "produto_id": produto.id,
                "sku": produto.sku,
                "tipo": produto.tipo,
                "status_ciclo": produto.status_ciclo,
                "saldos": saldos,
                "reservas_ativas": reservas,
                "custo_medio_global": custo_medio_global,
                "ruptura_potencial_30d": rupturas_30d,
                "atributos": atributos,
            }
        )


class ProdutoAtributoDefViewSet(viewsets.ModelViewSet):
    queryset = ProdutoAtributoDef.objects.all()
    serializer_class = ProdutoAtributoDefSerializer


class ProdutoAtributoValorViewSet(viewsets.ModelViewSet):
    queryset = ProdutoAtributoValor.objects.select_related("produto", "atributo_def")
    serializer_class = ProdutoAtributoValorSerializer
    filterset_fields = ["produto_id", "atributo_def_id"]


class ProdutoBOMItemViewSet(viewsets.ModelViewSet):
    queryset = ProdutoBOMItem.objects.select_related("produto_pai", "componente")
    serializer_class = ProdutoBOMItemSerializer
    filterset_fields = ["produto_pai_id", "componente_id", "ativo"]

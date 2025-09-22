from rest_framework import serializers

from estoque.models import (
    Deposito,
    EstoqueSaldo,
    InventarioCiclico,
    Lote,
    MovimentoEstoque,
    MovimentoEvidencia,
    NumeroSerie,
    PedidoSeparacao,
    PedidoSeparacaoAnexo,
    PedidoSeparacaoItem,
    PedidoSeparacaoMensagem,
    RegraReabastecimento,
    ReservaEstoque,
)


class DepositoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposito
        fields = ["id", "codigo", "nome", "tipo", "obra_id", "ativo"]


class EstoqueSaldoSerializer(serializers.ModelSerializer):
    produto_id = serializers.IntegerField()
    produto_nome = serializers.CharField(source="produto.nome", read_only=True)
    disponivel = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)

    class Meta:
        model = EstoqueSaldo
        fields = [
            "id",
            "produto_id",
            "produto_nome",
            "deposito_id",
            "quantidade",
            "reservado",
            "disponivel",
            "custo_medio",
            "atualizado_em",
        ]
        read_only_fields = ["custo_medio", "atualizado_em"]


class MovimentoEstoqueSerializer(serializers.ModelSerializer):
    lotes = serializers.SerializerMethodField()
    numeros_serie = serializers.SerializerMethodField()

    class Meta:
        model = MovimentoEstoque
        fields = [
            "id",
            "produto_id",
            "deposito_origem_id",
            "deposito_destino_id",
            "tipo",
            "quantidade",
            "custo_unitario_snapshot",
            "usuario_executante_id",
            "solicitante_tipo",
            "solicitante_id",
            "solicitante_nome_cache",
            "ref_externa",
            "motivo",
            "metadata",
            "reverso_de_id",
            "aprovacao_status",
            "aplicado",
            "aplicado_em",
            "valor_estimado",
            "criado_em",
            "lotes",
            "numeros_serie",
        ]
        read_only_fields = [
            "custo_unitario_snapshot",
            "criado_em",
            "aprovacao_status",
            "aplicado",
            "aplicado_em",
            "valor_estimado",
        ]

    def get_lotes(self, obj):
        return (
            [
                {"lote_id": ml.lote_id, "codigo": ml.lote.codigo, "quantidade": str(ml.quantidade)}
                for ml in obj.lotes_movimentados.all()
            ]
            if hasattr(obj, "lotes_movimentados")
            else []
        )

    def get_numeros_serie(self, obj):
        return (
            [
                {"numero_serie_id": mns.numero_serie_id, "codigo": mns.numero_serie.codigo}
                for mns in obj.numeros_serie_movimentados.all()
            ]
            if hasattr(obj, "numeros_serie_movimentados")
            else []
        )


class ReservaEstoqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservaEstoque
        fields = [
            "id",
            "produto_id",
            "deposito_id",
            "quantidade",
            "origem_tipo",
            "origem_id",
            "status",
            "expira_em",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["status", "criado_em", "atualizado_em"]


class PedidoSeparacaoItemSerializer(serializers.ModelSerializer):
    produto_nome = serializers.CharField(source="produto.nome", read_only=True)

    class Meta:
        model = PedidoSeparacaoItem
        fields = [
            "id",
            "produto_id",
            "produto_nome",
            "quantidade_solicitada",
            "quantidade_separada",
            "unidade_id",
            "observacao",
            "reserva_id",
            "status_item",
        ]
        read_only_fields = ["quantidade_separada", "reserva_id", "status_item"]


class PedidoSeparacaoSerializer(serializers.ModelSerializer):
    itens = PedidoSeparacaoItemSerializer(many=True, read_only=True)

    class Meta:
        model = PedidoSeparacao
        fields = [
            "id",
            "codigo",
            "solicitante_tipo",
            "solicitante_id",
            "solicitante_nome_cache",
            "prioridade",
            "status",
            "data_limite",
            "criado_por_user_id",
            "operador_responsavel_id",
            "itens_totais",
            "itens_pendentes",
            "itens_separados",
            "permitir_retirada_parcial",
            "canal_origem",
            "motivo_cancelamento",
            "metadata",
            "criado_em",
            "atualizado_em",
            "inicio_preparo",
            "pronto_em",
            "retirado_em",
            "itens",
        ]
        read_only_fields = [
            "codigo",
            "itens_totais",
            "itens_pendentes",
            "itens_separados",
            "criado_em",
            "atualizado_em",
            "inicio_preparo",
            "pronto_em",
            "retirado_em",
        ]


class PedidoSeparacaoMensagemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoSeparacaoMensagem
        fields = [
            "id",
            "pedido_id",
            "autor_user_id",
            "autor_tipo",
            "autor_id",
            "texto",
            "importante",
            "anexos_count",
            "metadata",
            "criado_em",
        ]
        read_only_fields = ["anexos_count", "criado_em"]


class MovimentoEvidenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimentoEvidencia
        fields = ["id", "movimento_id", "descricao", "arquivo", "criado_em"]
        read_only_fields = ["criado_em"]


class LoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lote
        fields = [
            "id",
            "produto_id",
            "codigo",
            "validade",
            "deposito_id",
            "quantidade_atual",
            "quantidade_reservada",
            "criado_em",
        ]
        read_only_fields = ["quantidade_atual", "quantidade_reservada", "criado_em"]


class PedidoSeparacaoAnexoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PedidoSeparacaoAnexo
        fields = ["id", "mensagem_id", "arquivo", "nome_original", "tamanho_bytes", "tipo_mime", "criado_em"]
        read_only_fields = ["criado_em"]


class NumeroSerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumeroSerie
        fields = ["id", "produto_id", "codigo", "status", "deposito_atual_id", "criado_em"]
        read_only_fields = ["criado_em"]


class RegraReabastecimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegraReabastecimento
        fields = [
            "id",
            "produto_id",
            "deposito_id",
            "estoque_min",
            "estoque_max",
            "lote_economico",
            "lead_time_dias",
            "estrategia",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["criado_em", "atualizado_em"]


class InventarioCiclicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventarioCiclico
        fields = [
            "id",
            "produto_id",
            "deposito_id",
            "periodicidade_dias",
            "ultima_contagem",
            "proxima_contagem",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["criado_em", "atualizado_em"]

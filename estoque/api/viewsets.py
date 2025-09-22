from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from estoque.models import (
    Deposito,
    EstoqueSaldo,
    InventarioCiclico,
    Lote,
    MovimentoEstoque,
    MovimentoEvidencia,
    NumeroSerie,
    PedidoSeparacao,
    PedidoSeparacaoItem,
    PedidoSeparacaoMensagem,
    RegraReabastecimento,
    ReservaEstoque,
)
from estoque.models import Deposito as DepModel
from estoque.services import movimentos as mov_srv
from estoque.services import pedidos_separacao as ps_srv
from estoque.services import reversao as rev_srv
from produtos.models import Produto
from shared.exceptions import MovimentoNaoReversivelError, NegocioError, SaldoInsuficienteError

from .serializers import (
    DepositoSerializer,
    EstoqueSaldoSerializer,
    InventarioCiclicoSerializer,
    LoteSerializer,
    MovimentoEstoqueSerializer,
    MovimentoEvidenciaSerializer,
    NumeroSerieSerializer,
    PedidoSeparacaoAnexoSerializer,
    PedidoSeparacaoItemSerializer,
    PedidoSeparacaoMensagemSerializer,
    PedidoSeparacaoSerializer,
    RegraReabastecimentoSerializer,
    ReservaEstoqueSerializer,
)


def produto_id_to_obj(pid):
    return Produto.objects.get(pk=pid)


def deposito_id_to_obj(did):
    return DepModel.objects.get(pk=did)


class DepositoViewSet(viewsets.ModelViewSet):
    queryset = Deposito.objects.all().order_by("id")
    serializer_class = DepositoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        serializer.save(tenant=tenant)


class EstoqueSaldoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EstoqueSaldo.objects.select_related("produto", "deposito").order_by("id")
    serializer_class = EstoqueSaldoSerializer
    filterset_fields = ["produto_id", "deposito_id"]

    @action(detail=False, methods=["get"])
    def kpis(self, request):
        from estoque.services.kpis import coletar_kpis

        data = coletar_kpis()
        return Response(data)

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs


class MovimentoEstoqueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimentoEstoque.objects.select_related(
        "produto", "deposito_origem", "deposito_destino", "usuario_executante"
    ).order_by("-criado_em", "-id")
    serializer_class = MovimentoEstoqueSerializer
    filterset_fields = ["produto_id", "tipo", "deposito_origem_id", "deposito_destino_id"]

    @action(detail=False, methods=["post"])
    def entrada(self, request):
        if not request.user.has_perm("estoque.pode_operar_movimento"):
            return Response({"detail": "Sem permissão para operar movimentos"}, status=403)
        data = request.data
        try:
            mov = mov_srv.registrar_entrada(
                produto_id_to_obj(data["produto_id"]),
                deposito_id_to_obj(data["deposito_id"]),
                Decimal(data["quantidade"]),
                Decimal(data["custo_unitario"]),
                request.user,
                tenant=getattr(request, "tenant", None),
                solicitante_tipo=data.get("solicitante_tipo"),
                solicitante_id=data.get("solicitante_id"),
                solicitante_nome_cache=data.get("solicitante_nome_cache"),
                motivo=data.get("motivo"),
                lotes=data.get("lotes"),
                numeros_serie=data.get("numeros_serie"),
            )
            return Response(MovimentoEstoqueSerializer(mov).data, status=201)
        except (NegocioError, SaldoInsuficienteError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=False, methods=["post"])
    def saida(self, request):
        if not request.user.has_perm("estoque.pode_operar_movimento"):
            return Response({"detail": "Sem permissão para operar movimentos"}, status=403)
        data = request.data
        try:
            mov = mov_srv.registrar_saida(
                produto_id_to_obj(data["produto_id"]),
                deposito_id_to_obj(data["deposito_id"]),
                Decimal(data["quantidade"]),
                request.user,
                tenant=getattr(request, "tenant", None),
                motivo=data.get("motivo"),
                solicitante_tipo=data.get("solicitante_tipo"),
                solicitante_id=data.get("solicitante_id"),
                solicitante_nome_cache=data.get("solicitante_nome_cache"),
                lotes=data.get("lotes"),
                numeros_serie=data.get("numeros_serie"),
            )
            return Response(MovimentoEstoqueSerializer(mov).data, status=201)
        except (NegocioError, SaldoInsuficienteError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=False, methods=["post"])
    def transferencia(self, request):
        if not request.user.has_perm("estoque.pode_operar_movimento"):
            return Response({"detail": "Sem permissão para operar movimentos"}, status=403)
        data = request.data
        try:
            mov = mov_srv.transferir(
                produto_id_to_obj(data["produto_id"]),
                deposito_id_to_obj(data["deposito_origem_id"]),
                deposito_id_to_obj(data["deposito_destino_id"]),
                Decimal(data["quantidade"]),
                request.user,
                motivo=data.get("motivo"),
            )
            return Response(MovimentoEstoqueSerializer(mov).data, status=201)
        except (NegocioError, SaldoInsuficienteError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reverter(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_aprovar_movimento"):
            return Response({"detail": "Sem permissão para reverter movimentos"}, status=403)
        mov = self.get_object()
        try:
            reverso = rev_srv.reverter_movimento(mov, request.user)
            return Response(MovimentoEstoqueSerializer(reverso).data, status=201)
        except (NegocioError, MovimentoNaoReversivelError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=False, methods=["post"])
    def descarte(self, request):
        if not request.user.has_perm("estoque.pode_operar_movimento"):
            return Response({"detail": "Sem permissão para operar movimentos"}, status=403)
        data = request.data
        from estoque.services import descartes

        try:
            mov = descartes.registrar_descarte(
                produto_id_to_obj(data["produto_id"]),
                deposito_id_to_obj(data["deposito_id"]),
                Decimal(data["quantidade"]),
                request.user,
                data.get("justificativa", ""),
                tipo=data.get("tipo", "DESCARTE"),
                threshold_aprovacao_valor=Decimal(str(data.get("threshold_valor", "0"))),
                lotes=data.get("lotes"),
                tenant=getattr(request, "tenant", None),
                evidencias_ids=data.get("evidencias_ids"),
                valor_perda_minimo_evidencia=Decimal(str(data.get("valor_perda_minimo_evidencia", "0"))),
            )
            return Response(MovimentoEstoqueSerializer(mov).data, status=201)
        except (NegocioError, SaldoInsuficienteError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=False, methods=["post"])
    def consumo_bom(self, request):
        if not request.user.has_perm("estoque.pode_consumir_bom"):
            return Response({"detail": "Sem permissão para consumo BOM"}, status=403)
        data = request.data
        from estoque.services.bom import consumir_bom

        try:
            movimentos = consumir_bom(
                produto_id_to_obj(data["produto_id_final"]),
                deposito_id_to_obj(data["deposito_id"]),
                Decimal(data["quantidade_final"]),
                request.user,
                origem_tipo=data.get("origem_tipo"),
                origem_id=data.get("origem_id"),
            )
            return Response(MovimentoEstoqueSerializer(movimentos, many=True).data, status=201)
        except NotImplementedError as e:
            return Response({"detail": str(e)}, status=501)
        except (NegocioError, SaldoInsuficienteError) as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def aprovar(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_aprovar_movimento"):
            return Response({"detail": "Sem permissão para aprovar movimentos"}, status=403)
        mov = self.get_object()
        from estoque.services.descartes import aprovar_movimento_perda

        try:
            aprovar_movimento_perda(mov, request.user)
            return Response(MovimentoEstoqueSerializer(mov).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def rejeitar(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_aprovar_movimento"):
            return Response({"detail": "Sem permissão para rejeitar movimentos"}, status=403)
        mov = self.get_object()
        from estoque.services.descartes import rejeitar_movimento_perda

        try:
            rejeitar_movimento_perda(mov, request.user, request.data.get("motivo", ""))
            return Response(MovimentoEstoqueSerializer(mov).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)


class ReservaEstoqueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReservaEstoque.objects.select_related("produto", "deposito")
    serializer_class = ReservaEstoqueSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs


class MovimentoEvidenciaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimentoEvidencia.objects.select_related("movimento")
    serializer_class = MovimentoEvidenciaSerializer
    filterset_fields = ["movimento_id"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs


class LoteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Lote.objects.select_related("produto")
    serializer_class = LoteSerializer
    filterset_fields = ["produto_id", "codigo"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs


class NumeroSerieViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NumeroSerie.objects.select_related("produto", "deposito_atual")
    serializer_class = NumeroSerieSerializer
    filterset_fields = ["produto_id", "status", "deposito_atual_id"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs


class RegraReabastecimentoViewSet(viewsets.ModelViewSet):
    queryset = RegraReabastecimento.objects.select_related("produto", "deposito")
    serializer_class = RegraReabastecimentoSerializer
    filterset_fields = ["produto_id", "deposito_id", "ativo"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs

    def perform_create(self, serializer):
        if not self.request.user.has_perm("estoque.pode_gerenciar_reabastecimento"):
            raise PermissionError("Sem permissão para gerenciar reabastecimento")
        tenant = getattr(self.request, "tenant", None)
        serializer.save(tenant=tenant)


class InventarioCiclicoViewSet(viewsets.ModelViewSet):
    queryset = InventarioCiclico.objects.select_related("produto", "deposito")
    serializer_class = InventarioCiclicoSerializer
    filterset_fields = ["produto_id", "deposito_id", "ativo"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs

    def perform_create(self, serializer):
        if not self.request.user.has_perm("estoque.pode_gerenciar_inventario_ciclico"):
            raise PermissionError("Sem permissão para gerenciar inventário cíclico")
        tenant = getattr(self.request, "tenant", None)
        serializer.save(tenant=tenant)


class PedidoSeparacaoViewSet(viewsets.ModelViewSet):
    queryset = PedidoSeparacao.objects.prefetch_related("itens")
    serializer_class = PedidoSeparacaoSerializer
    filterset_fields = ["status", "prioridade", "solicitante_tipo", "solicitante_id"]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs

    def create(self, request, *args, **kwargs):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão para criar picking"}, status=403)
        data = request.data
        itens_payload = data.get("itens", [])
        max_urgentes = int(data.get("max_urgentes", 5))
        from estoque.models import Unidade
        from produtos.models import Produto

        itens = []
        for it in itens_payload:
            itens.append(
                {
                    "produto": Produto.objects.get(pk=it["produto_id"]),
                    "quantidade": Decimal(it["quantidade"]),
                    "unidade": Unidade.objects.get(pk=it["unidade_id"]) if it.get("unidade_id") else None,
                }
            )
        from shared.exceptions import NegocioError

        try:
            pedido = ps_srv.criar_pedido(
                data["solicitante_tipo"],
                data["solicitante_id"],
                data["solicitante_nome_cache"],
                itens,
                prioridade=data.get("prioridade", "NORMAL"),
                criado_por=request.user,
                permitir_retirada_parcial=data.get("permitir_retirada_parcial", False),
                tenant=getattr(request, "tenant", None),
                max_urgentes=max_urgentes,
            )
            return Response(PedidoSeparacaoSerializer(pedido).data, status=201)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão"}, status=403)
        pedido = self.get_object()
        try:
            ps_srv.iniciar_preparacao(pedido, request.user)
            return Response(PedidoSeparacaoSerializer(pedido).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def concluir(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão"}, status=403)
        pedido = self.get_object()
        try:
            ps_srv.concluir_pedido(pedido)
            return Response(PedidoSeparacaoSerializer(pedido).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def retirar(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão"}, status=403)
        pedido = self.get_object()
        try:
            ps_srv.registrar_retirada(pedido)
            return Response(PedidoSeparacaoSerializer(pedido).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def mensagem(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão"}, status=403)
        pedido = self.get_object()
        try:
            msg = ps_srv.adicionar_mensagem(pedido, request.data.get("texto", ""), autor_user=request.user)
            return Response(PedidoSeparacaoMensagemSerializer(msg).data, status=201)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"])
    def anexar(self, request, pk=None):
        if not request.user.has_perm("estoque.pode_gerenciar_picking"):
            return Response({"detail": "Sem permissão"}, status=403)
        pedido = self.get_object()
        mensagem_id = request.data.get("mensagem_id")
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response({"detail": "Arquivo obrigatório"}, status=400)
        from estoque.models import PedidoSeparacaoAnexo

        mensagem = get_object_or_404(PedidoSeparacaoMensagem, pk=mensagem_id, pedido=pedido)
        anexo = PedidoSeparacaoAnexo.objects.create(
            mensagem=mensagem,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tamanho_bytes=arquivo.size,
            tipo_mime=getattr(arquivo, "content_type", "application/octet-stream"),
            tenant=pedido.tenant,
        )
        mensagem.anexos_count = mensagem.anexos.count()
        mensagem.save(update_fields=["anexos_count"])
        return Response(PedidoSeparacaoAnexoSerializer(anexo).data, status=201)


class PedidoSeparacaoItemViewSet(viewsets.ModelViewSet):
    queryset = PedidoSeparacaoItem.objects.select_related("pedido", "produto")
    serializer_class = PedidoSeparacaoItemSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs

    def partial_update(self, request, *args, **kwargs):
        item = self.get_object()
        acao = request.data.get("acao")
        from shared.exceptions import NegocioError

        try:
            if acao == "separar":
                from estoque.services import pedidos_separacao as ps_srv

                ps_srv.marcar_item_separado(item, Decimal(request.data.get("quantidade", "0")))
            elif acao == "indisponivel":
                from estoque.services import pedidos_separacao as ps_srv

                ps_srv.marcar_item_indisponivel(item, request.data.get("observacao", ""))
            else:
                return Response({"detail": "Ação inválida"}, status=400)
            return Response(PedidoSeparacaoItemSerializer(item).data)
        except NegocioError as e:
            return Response({"detail": str(e)}, status=400)


## (helpers movidos para o topo do arquivo)

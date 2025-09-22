# funcionarios/api.py

from datetime import date

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Beneficio, CartaoPonto, Ferias, Funcionario, SalarioHistorico
from .serializers import (
    BeneficioSerializer,
    CartaoPontoSerializer,
    FeriasSerializer,
    FuncionarioSerializer,
)
from .utils import (
    CalculadoraFerias,
    CalculadoraFGTS,
    CalculadoraINSS,
    CalculadoraIRRF,
    CalculadoraMaoObra,
)


class FuncionarioViewSet(viewsets.ModelViewSet):
    """ViewSet para API de funcionários"""

    queryset = Funcionario.objects.all()  # Necessário para DRF router determinar basename
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = Funcionario.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=["get"])
    def calcular_custos(self, request, pk=None):
        """Calcula custos de mão de obra do funcionário"""
        funcionario = self.get_object()
        custos = CalculadoraMaoObra.calcular_custo_total(funcionario)

        return Response({"funcionario": funcionario.nome_completo, "custos": custos})

    @action(detail=True, methods=["get"])
    def calcular_impostos(self, request, pk=None):
        """Calcula impostos e contribuições do funcionário"""
        funcionario = self.get_object()
        salario = funcionario.get_salario_atual()

        inss = CalculadoraINSS.calcular(salario)
        fgts = CalculadoraFGTS.calcular(salario)
        irrf = CalculadoraIRRF.calcular(salario, funcionario.numero_dependentes)

        return Response(
            {
                "funcionario": funcionario.nome_completo,
                "salario_base": salario,
                "inss": inss,
                "fgts": fgts,
                "irrf": irrf,
            }
        )

    @action(detail=True, methods=["post"])
    def registrar_ponto(self, request, pk=None):
        """Registra ponto para o funcionário"""
        funcionario = self.get_object()

        tipo_registro = request.data.get("tipo_registro")
        justificativa = request.data.get("justificativa", "")
        localizacao = request.data.get("localizacao", "")

        if not tipo_registro:
            return Response({"error": "tipo_registro é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)

        # Obtém IP do request
        ip_origem = request.META.get("REMOTE_ADDR")

        registro = CartaoPonto.objects.create(
            tenant=funcionario.tenant,
            funcionario=funcionario,
            data_hora_registro=timezone.now(),
            tipo_registro=tipo_registro,
            ip_origem=ip_origem,
            localizacao=localizacao,
            justificativa=justificativa,
            aprovado=True,  # Auto-aprovado por padrão
        )

        serializer = CartaoPontoSerializer(registro)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def historico_salarial(self, request, pk=None):
        """Retorna histórico salarial do funcionário"""
        funcionario = self.get_object()

        historico = SalarioHistorico.objects.filter(funcionario=funcionario).order_by("-data_vigencia")

        data = []
        for item in historico:
            data.append(
                {
                    "data_vigencia": item.data_vigencia,
                    "valor_salario": item.valor_salario,
                    "motivo_alteracao": item.motivo_alteracao,
                    "alterado_por": item.alterado_por.get_full_name() if item.alterado_por else None,
                }
            )

        return Response(data)


class FeriasViewSet(viewsets.ModelViewSet):
    """ViewSet para API de férias"""

    queryset = Ferias.objects.all()
    serializer_class = FeriasSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = Ferias.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=["post"])
    def calcular_valor(self, request, pk=None):
        """Calcula valor das férias"""
        ferias = self.get_object()

        valores = CalculadoraFerias.calcular_valor_ferias(
            ferias.funcionario.get_salario_atual(),
            ferias.dias_gozados,
            ferias.dias_abono if ferias.abono_pecuniario else 0,
        )

        return Response({"ferias_id": ferias.id, "valores": valores})

    @action(detail=False, methods=["get"])
    def vencidas(self, request):
        """Lista férias vencidas"""
        from dateutil.relativedelta import relativedelta

        data_limite = date.today() - relativedelta(months=12)

        # Lógica para identificar férias vencidas
        # (implementação simplificada)

        return Response({"data_limite": data_limite, "message": "Funcionalidade em desenvolvimento"})


class CartaoPontoViewSet(viewsets.ModelViewSet):
    """ViewSet para API de cartão de ponto"""

    queryset = CartaoPonto.objects.all()
    serializer_class = CartaoPontoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = CartaoPonto.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        # Adiciona IP automaticamente
        ip_origem = self.request.META.get("REMOTE_ADDR")
        serializer.save(tenant=self.request.user.tenant, ip_origem=ip_origem)

    @action(detail=False, methods=["post"])
    def registrar(self, request):
        """Endpoint simplificado para registrar ponto"""
        funcionario_id = request.data.get("funcionario_id")
        tipo_registro = request.data.get("tipo_registro")

        if not funcionario_id or not tipo_registro:
            return Response(
                {"error": "funcionario_id e tipo_registro são obrigatórios"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            funcionario = Funcionario.objects.get(id=funcionario_id, tenant=request.user.tenant)
        except Funcionario.DoesNotExist:
            return Response({"error": "Funcionário não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        ip_origem = request.META.get("REMOTE_ADDR")

        registro = CartaoPonto.objects.create(
            tenant=request.user.tenant,
            funcionario=funcionario,
            data_hora_registro=timezone.now(),
            tipo_registro=tipo_registro,
            ip_origem=ip_origem,
            justificativa=request.data.get("justificativa", ""),
            localizacao=request.data.get("localizacao", ""),
            aprovado=True,
        )

        serializer = self.get_serializer(registro)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BeneficioViewSet(viewsets.ModelViewSet):
    """ViewSet para API de benefícios"""

    queryset = Beneficio.objects.all()
    serializer_class = BeneficioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = Beneficio.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=False, methods=["post"])
    def calcular_folha(self, request):
        """Calcula folha de pagamento para um mês"""
        mes = request.data.get("mes", timezone.now().month)
        ano = request.data.get("ano", timezone.now().year)
        funcionario_id = request.data.get("funcionario_id")

        try:
            mes = int(mes)
            ano = int(ano)
        except (ValueError, TypeError):
            return Response({"error": "Mês e ano devem ser números inteiros"}, status=status.HTTP_400_BAD_REQUEST)

        data_referencia = date(ano, mes, 1)

        # Filtrar funcionários
        funcionarios = Funcionario.objects.filter(tenant=request.user.tenant, ativo=True)

        if funcionario_id:
            funcionarios = funcionarios.filter(id=funcionario_id)

        resultados = []

        for funcionario in funcionarios:
            salario = funcionario.get_salario_atual()

            inss = CalculadoraINSS.calcular(salario)
            fgts = CalculadoraFGTS.calcular(salario)
            irrf = CalculadoraIRRF.calcular(salario, funcionario.numero_dependentes)

            resultados.append(
                {
                    "funcionario_id": funcionario.id,
                    "funcionario_nome": funcionario.nome_completo,
                    "salario_base": salario,
                    "inss": inss,
                    "fgts": fgts,
                    "irrf": irrf,
                    "salario_liquido": salario - inss["valor_desconto"] - irrf["valor_irrf"],
                }
            )

        return Response({"mes": mes, "ano": ano, "data_referencia": data_referencia, "funcionarios": resultados})

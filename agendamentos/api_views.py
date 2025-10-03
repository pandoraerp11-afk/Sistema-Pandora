"""Este módulo contém as views da API para o app de agendamentos."""

import contextlib
from typing import ClassVar, cast

from django.conf import settings as dj_settings
from django.contrib.auth.models import AbstractUser, User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Model, QuerySet, Sum
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import AcessoCliente, Cliente
from core.models import Tenant as _Tenant
from core.utils import get_current_tenant
from servicos.models import Servico as _Servico
from shared.permissions_servicos import CLINICAL_SCHEDULING_DENIED_MESSAGE, can_schedule_clinical_service

from .models import Agendamento, AuditoriaAgendamento, Disponibilidade, ProfissionalProcedimento, Slot
from .serializers import (
    AgendamentoSerializer,
    AgendamentoV2CreateSerializer,
    AgendamentoV2DetailSerializer,
    AgendamentoV2ListSerializer,
    AuditoriaAgendamentoSerializer,
    DisponibilidadeSerializer,
    SlotSerializer,
)
from .services import AgendamentoService, SchedulingService, SlotService, get_slots_cache_version


def _get_permission_codename(action: str, model: type[Model]) -> str:
    """Retorna o codinome da permissão para uma determinada ação e modelo."""
    # Acesso intencional a _meta para interoperabilidade com sistema de permissões do Django.
    return f"{model._meta.app_label}.{action}_{model._meta.model_name}"  # noqa: SLF001


class IsAgendamentoProfissionalOuSecretaria(permissions.BasePermission):
    """Permissão para verificar se o usuário é um profissional ou secretária.

    Concede acesso a superusuários, secretárias, ou a profissionais com
    permissões de modelo específicas (se ativado).
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Verifica se o usuário tem permissão para a requisição."""
        user = request.user
        if not isinstance(user, AbstractUser):
            return False

        if user.is_superuser or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists():
            return True

        if user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists():
            return request.method in permissions.SAFE_METHODS

        if not user.is_staff or not getattr(dj_settings, "ENABLE_AGENDAMENTOS_MODEL_PERMS", False):
            return user.is_staff

        try:
            model = view.queryset.model
            method_map = {
                "GET": "view",
                "HEAD": "view",
                "OPTIONS": "view",
                "POST": "add",
                "PUT": "change",
                "PATCH": "change",
                "DELETE": "delete",
            }
            needed_perm = method_map.get(request.method, "view")
            perm_codename = _get_permission_codename(needed_perm, model)
            return user.has_perm(perm_codename)
        except AttributeError:
            return True

    def has_object_permission(self, request: Request, view: APIView, _obj: Model) -> bool:
        """Verifica a permissão no nível do objeto, reutilizando a lógica de `has_permission`."""
        return self.has_permission(request, view)


class IsAgendamentoAuditoria(permissions.BasePermission):
    """Restringe acesso à auditoria: somente superuser ou grupo secretaria."""

    def has_permission(self, request: Request, _view: APIView) -> bool:
        """Verifica se o usuário tem permissão para acessar a auditoria."""
        user = request.user
        if not isinstance(user, AbstractUser):
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()


class IsClientePortal(permissions.BasePermission):
    """Permite acesso a usuários autenticados que tenham vínculo de portal com algum Cliente no tenant atual."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Verifica se o usuário é um cliente do portal com acesso."""
        user = request.user
        if not isinstance(user, AbstractUser):
            return False
        if user.is_staff or user.is_superuser:
            return False

        tenant = get_current_tenant(request._request)  # noqa: SLF001
        if not tenant:
            pk = view.kwargs.get("pk")
            if pk:
                with contextlib.suppress(Slot.DoesNotExist, AttributeError):
                    slot = Slot.objects.select_related("tenant").get(id=pk)
                    if slot.tenant and hasattr(request, "session"):
                        request.session["tenant_id"] = slot.tenant_id
                        tenant = slot.tenant

        if not tenant:
            return AcessoCliente.objects.filter(usuario=user, cliente__status="active").exists()
        return AcessoCliente.objects.filter(usuario=user, cliente__tenant=tenant, cliente__status="active").exists()


def _resolver_cliente_do_usuario(request: Request) -> Cliente | None:
    """Retorna o Cliente associado ao usuário autenticado no tenant atual.

    Se múltiplos, aceita request.data['cliente_id'] contanto que pertença ao
    conjunto permitido.
    """
    drf_request = request
    if not isinstance(drf_request, Request):
        drf_request = Request(request)

    tenant = get_current_tenant(drf_request._request)  # noqa: SLF001
    if not tenant:
        return None
    user = drf_request.user
    if not isinstance(user, AbstractUser):
        return None
    cid = drf_request.data.get("cliente_id") or drf_request.query_params.get("cliente_id")
    base_qs = Cliente.objects.filter(tenant=tenant, acessos__usuario=user, status="active").distinct()
    if cid:
        return base_qs.filter(id=cid).first()
    return base_qs.first()


class DisponibilidadeViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar Disponibilidades."""

    queryset = Disponibilidade.objects.all()
    serializer_class = DisponibilidadeSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [
        permissions.IsAuthenticated,
        IsAgendamentoProfissionalOuSecretaria,
    ]

    def get_queryset(self) -> QuerySet[Disponibilidade]:
        """Filtra o queryset para o tenant e usuário atuais."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        if not tenant:
            return Disponibilidade.objects.none()

        user = self.request.user
        if not isinstance(user, AbstractUser):
            return Disponibilidade.objects.none()

        qs_base = Disponibilidade.objects.filter(tenant=tenant, ativo=True)

        # Otimização de cache para leitura
        if self.request.method == "GET":
            papel = "adm" if self._is_admin(user) else "prof"
            cache_key = f"ag:disp:{tenant.id}:{papel}:{get_slots_cache_version()}"
            if cached_ids := cache.get(cache_key):
                return qs_base.filter(id__in=cached_ids)

        qs = self._filter_queryset_by_user(qs_base, user)

        # Salva no cache após filtrar
        if self.request.method == "GET":
            papel = "adm" if self._is_admin(user) else "prof"
            cache_key = f"ag:disp:{tenant.id}:{papel}:{get_slots_cache_version()}"
            with contextlib.suppress(Exception):
                cache.set(cache_key, list(qs.values_list("id", flat=True)), 30)

        return qs

    def _is_admin(self, user: AbstractUser) -> bool:
        """Verifica se o usuário tem perfil de administrador para agendamentos."""
        return (
            user.is_superuser
            or user.groups.filter(
                name__in=["AGENDAMENTOS_SECRETARIA", "AGENDAMENTOS_VISUALIZAR"],
            ).exists()
        )

    def _filter_queryset_by_user(
        self,
        queryset: QuerySet[Disponibilidade],
        user: AbstractUser,
    ) -> QuerySet[Disponibilidade]:
        """Filtra o queryset de acordo com o perfil do usuário."""
        if self._is_admin(user):
            return queryset
        return queryset.filter(profissional=user)

    def perform_create(self, serializer: drf_serializers.Serializer) -> None:
        """Define o tenant e o profissional ao criar uma disponibilidade."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        user = self.request.user
        if not tenant:
            msg = "Tenant inválido"
            raise permissions.PermissionDenied(msg)
        if not isinstance(user, AbstractUser):
            msg = "Usuário inválido"
            raise permissions.PermissionDenied(msg)

        if not serializer.validated_data:
            msg = "Dados de validação não encontrados."
            raise drf_serializers.ValidationError(msg)

        profissional = serializer.validated_data.get("profissional", user)
        serializer.save(
            tenant=tenant,
            profissional=user if not user.is_superuser else profissional,
        )

    def perform_update(self, serializer: drf_serializers.Serializer) -> None:
        """Atualiza a instância da disponibilidade."""
        serializer.save()

    @action(detail=True, methods=["post"])
    def gerar_slots(self, request: Request, pk: str | None = None) -> Response:
        """Gera slots para uma disponibilidade específica."""
        del request, pk
        disp = self.get_object()
        criados, existentes = SlotService.gerar_slots(disp)
        return Response({"disponibilidade": disp.id, "criados": criados, "ja_existentes": existentes})


class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para visualização de Slots."""

    queryset = Slot.objects.select_related("profissional", "disponibilidade").all()
    serializer_class = SlotSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [
        permissions.IsAuthenticated,
        IsAgendamentoProfissionalOuSecretaria,
    ]

    def get_queryset(self) -> QuerySet[Slot]:
        """Filtra slots para o tenant e usuário atuais."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        qs_base = Slot.objects.filter(tenant=tenant, ativo=True)
        # Filtros opcionais
        prof_id = self.request.query_params.get("profissional")
        data = self.request.query_params.get("data")
        disponivel = self.request.query_params.get("disponivel")

        # Cache somente para leitura (não para superuser com alterações frequentes) - inclui filtros
        cache_key = None
        if tenant and self.request.method == "GET":
            user = self.request.user
            if isinstance(user, AbstractUser):
                papel = (
                    "adm"
                    if user.is_superuser or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
                    else "prof"
                )
                cache_key = (
                    f"ag:disp:{tenant.id}:{papel}:{prof_id or '-'}:{data or '-'}:{disponivel or '-'}:"
                    f"{get_slots_cache_version()}"
                )
                if data_ids := cache.get(cache_key):
                    return qs_base.filter(id__in=data_ids)

        user = self.request.user
        if not isinstance(user, AbstractUser):
            return qs_base.none()

        if (
            user.is_superuser
            or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
            or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
        ):
            final_qs = qs_base
        else:
            final_qs = qs_base.filter(profissional=user)

        # Aplicar filtros opcionais
        if prof_id:
            final_qs = final_qs.filter(profissional_id=prof_id)
        if data:
            final_qs = final_qs.filter(horario__date=data)
        if disponivel in {"1", "true", "True"}:
            final_qs = final_qs.filter(capacidade_utilizada__lt=F("capacidade_total"))

        if cache_key:
            with contextlib.suppress(Exception):
                cache.set(cache_key, list(final_qs.values_list("id", flat=True)), 30)
        return final_qs

    def get_object(self) -> Slot:
        """Obtém um slot, com fallback para ajustar o tenant na sessão."""
        try:
            return super().get_object()
        except Http404:
            pk = self.kwargs.get(self.lookup_field or "pk")
            slot = Slot.objects.filter(pk=pk).select_related("profissional", "disponibilidade").first()
            if not slot:
                raise
            req = self.request
            if not hasattr(req, "session"):
                req.session = {}
            if slot.tenant_id and req.session.get("tenant_id") != slot.tenant_id:
                req.session["tenant_id"] = slot.tenant_id
            return slot

    @action(detail=True, methods=["post"])
    def reservar(self, request: Request, pk: str | None = None) -> Response:
        """Reserva um slot para um cliente."""
        del pk
        slot = self.get_object()
        if not hasattr(request, "session"):
            request.session = {}
        if "tenant_id" not in request.session and slot.tenant_id:
            request.session["tenant_id"] = slot.tenant_id

        cliente_id = request.data.get("cliente_id")
        if not cliente_id:
            msg = "cliente_id obrigatório"
            return Response({"detail": _(msg)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente = Cliente.objects.get(id=cliente_id, tenant=slot.tenant)
        except Cliente.DoesNotExist as e:
            raise Http404 from e

        servico_id = request.data.get("servico_id")
        if servico_id:
            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
                if _serv.is_clinical and not can_schedule_clinical_service(request.user, _serv):
                    return Response(
                        {"detail": str(CLINICAL_SCHEDULING_DENIED_MESSAGE)},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except _Servico.DoesNotExist:
                msg = "Serviço inválido"
                return Response({"detail": _(msg)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ag = AgendamentoService.criar(
                tenant=slot.tenant,
                cliente=cliente,
                profissional=slot.profissional,
                data_inicio=slot.horario,
                data_fim=None,
                origem="OPERADOR" if request.user.is_staff else "CLIENTE",
                slot=slot,
                servico=servico_id,
                metadata={"atalho_reserva": True},
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ser = AgendamentoSerializer(ag)
        return Response({"slot": slot.id, "agendamento": ser.data})

    @action(detail=True, methods=["post"])
    def waitlist(self, request: Request, pk: str | None = None) -> Response:
        """Adiciona um cliente à lista de espera de um slot."""
        del pk
        slot = self.get_object()
        cliente_id = request.data.get("cliente_id")
        if not cliente_id:
            msg = "cliente_id obrigatório"
            return Response({"detail": _(msg)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente = Cliente.objects.get(id=cliente_id, tenant=slot.tenant)
        except Cliente.DoesNotExist:
            msg = "cliente inválido"
            return Response({"detail": _(msg)}, status=status.HTTP_400_BAD_REQUEST)

        prioridade = int(request.data.get("prioridade", 100))
        try:
            wl = AgendamentoService.inscrever_waitlist(slot, cliente=cliente, prioridade=prioridade)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"waitlist_id": wl.id, "prioridade": wl.prioridade})


class AgendamentoViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar Agendamentos."""

    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [
        permissions.IsAuthenticated,
        IsAgendamentoProfissionalOuSecretaria,
    ]

    def get_queryset(self) -> QuerySet[Agendamento]:
        """Filtra agendamentos para o tenant e usuário atuais."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        qs = Agendamento.objects.filter(tenant=tenant).order_by("data_inicio", "id")
        user = self.request.user
        if not isinstance(user, AbstractUser):
            return qs.none()
        if (
            user.is_superuser
            or user.groups.filter(name="AGENDAMENTOS_SECRETARIA").exists()
            or user.groups.filter(name="AGENDAMENTOS_VISUALIZAR").exists()
        ):
            return qs
        if user.is_staff:
            return qs.filter(profissional=user)
        return qs.none()

    def _validate_agendamento_data(self, validated_data: dict, user: AbstractUser) -> None:
        """Valida os dados necessários para criar um agendamento."""
        slot = validated_data.get("slot")
        data_inicio = validated_data.get("data_inicio")
        data_fim = validated_data.get("data_fim")

        if not slot and (not data_inicio or not data_fim):
            msg = "Para agendamento manual informe data_inicio e data_fim"
            raise permissions.PermissionDenied(msg)

        servico_id = self.request.data.get("servico_id")
        if servico_id:
            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
                if _serv.is_clinical and not can_schedule_clinical_service(cast("User", user), _serv):
                    raise permissions.PermissionDenied(str(CLINICAL_SCHEDULING_DENIED_MESSAGE))
            except _Servico.DoesNotExist as e:
                msg = "Serviço inválido"
                raise permissions.PermissionDenied(msg) from e

    def perform_create(self, serializer: drf_serializers.Serializer) -> None:
        """Criação centralizada usando service para garantir regras.

        Replica lógica essencial da v2 evitando duplicação de regras de negócio.
        """
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        if tenant is None:
            with contextlib.suppress(AttributeError, _Tenant.DoesNotExist):
                sid = getattr(self.request, "session", {}).get("tenant_id")
                if sid:
                    tenant = _Tenant.objects.get(id=sid)

        user = self.request.user
        if not tenant:
            msg = "Tenant inválido"
            raise permissions.PermissionDenied(msg)
        if not isinstance(user, AbstractUser):
            msg = "Usuário inválido"
            raise permissions.PermissionDenied(msg)

        validated_data = serializer.validated_data
        validated_data = serializer.validated_data
        if not isinstance(validated_data, dict):
            msg = "Dados de validação não encontrados."
            raise drf_serializers.ValidationError(msg)

        self._validate_agendamento_data(validated_data, user)

        try:
            with transaction.atomic():
                slot = validated_data.get("slot")
                profissional = validated_data.get("profissional")
                if not profissional:
                    profissional = slot.profissional if slot else user

                data_inicio = validated_data.get("data_inicio")
                if not data_inicio:
                    msg = "Data de início é obrigatória."
                    raise drf_serializers.ValidationError(msg)

                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=validated_data.get("cliente"),
                    profissional=profissional,
                    data_inicio=data_inicio,
                    data_fim=validated_data.get("data_fim"),
                    origem=validated_data.get("origem") or ("PROFISSIONAL" if user.is_staff else "CLIENTE"),
                    slot=slot,
                    servico=self.request.data.get("servico_id"),
                    metadata=validated_data.get("metadata"),
                    user=user,
                )
        except (ValueError, TypeError) as e:
            raise drf_serializers.ValidationError({"detail": str(e)}) from e
        serializer.instance = ag

    @action(detail=True, methods=["post"])
    def cancelar(self, request: Request, pk: str | None = None) -> Response:
        """Cancela um agendamento."""
        del pk
        ag = self.get_object()
        motivo = request.data.get("motivo") or "Cancelado via API"
        try:
            AgendamentoService.cancelar(ag, motivo=motivo, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok", "novo_status": ag.status})

    @action(detail=True, methods=["post"])
    def reagendar(self, request: Request, pk: str | None = None) -> Response:
        """Reagenda um agendamento para um novo slot ou horário."""
        del pk
        ag = self.get_object()
        novo_slot_id = request.data.get("novo_slot")
        nova_data_inicio_str = request.data.get("nova_data_inicio")
        nova_data_fim_str = request.data.get("nova_data_fim")
        motivo = request.data.get("motivo") or "Reagendamento via API"

        novo_slot = None
        if novo_slot_id:
            novo_slot = Slot.objects.filter(id=novo_slot_id, tenant=ag.tenant, ativo=True).first()
            if not novo_slot:
                return Response({"detail": "novo_slot inválido"}, status=status.HTTP_400_BAD_REQUEST)

        nova_data_inicio = parse_datetime(nova_data_inicio_str) if nova_data_inicio_str else None
        nova_data_fim = parse_datetime(nova_data_fim_str) if nova_data_fim_str else None

        try:
            novo = AgendamentoService.reagendar(
                ag,
                novo_slot=novo_slot,
                nova_data_inicio=nova_data_inicio,
                nova_data_fim=nova_data_fim,
                user=request.user,
                motivo=motivo,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ser = self.get_serializer(novo)
        return Response(ser.data)

    @action(detail=True, methods=["post"])
    def checkin(self, request: Request, pk: str | None = None) -> Response:
        """Realiza o check-in de um agendamento."""
        del pk
        ag = self.get_object()
        try:
            AgendamentoService.checkin(ag, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": ag.status})

    @action(detail=True, methods=["post"])
    def concluir(self, request: Request, pk: str | None = None) -> Response:
        """Marca um agendamento como concluído."""
        del pk
        ag = self.get_object()
        try:
            AgendamentoService.concluir(ag, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": ag.status})

    @action(detail=True, methods=["post"])
    def resolver_pendencias(self, request: Request, pk: str | None = None) -> Response:
        """Resolve pendências de um agendamento."""
        del pk
        ag = self.get_object()
        AgendamentoService.resolver_pendencias(ag, user=request.user)
        return Response({"status": ag.status, "metadata": ag.metadata})

    @action(detail=True, methods=["post"])
    def sync_evento(self, request: Request, pk: str | None = None) -> Response:
        """Força sincronização manual do evento espelho.

        Retorna o id do evento criado/atualizado ou null se desabilitado.
        """
        del request, pk
        ag = self.get_object()
        evento_id = SchedulingService.sync_evento(ag)
        return Response({"agendamento": ag.id, "evento_id": evento_id})


class AgendamentoV2ViewSet(AgendamentoViewSet):
    """Versão 2 do ViewSet de Agendamento.

    Permite evolução de payloads/serializers sem quebrar clientes antigos.
    Controlado por flag USE_NOVO_AGENDAMENTO para ativação gradual nas rotas.
    """

    def get_queryset(self) -> QuerySet[Agendamento]:
        """Retorna o queryset para a V2, respeitando a feature flag."""
        qs = super().get_queryset()
        if not getattr(dj_settings, "USE_NOVO_AGENDAMENTO", False):
            return qs.none()
        return qs

    def get_serializer_class(self) -> type[drf_serializers.Serializer]:
        """Retorna a classe do serializador com base na ação."""
        if self.action in ("list", "stats", "capacidade"):
            return AgendamentoV2ListSerializer
        if self.action == "retrieve":
            return AgendamentoV2DetailSerializer
        if self.action == "create":
            return AgendamentoV2CreateSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["get"])
    def stats(self, request: Request) -> Response:
        """Retorna estatísticas sobre os agendamentos."""
        tenant = get_current_tenant(request._request)  # noqa: SLF001
        now = timezone.now()
        qs = Agendamento.objects.filter(tenant=tenant)
        futuro = qs.filter(data_inicio__gte=now)
        no_show = qs.filter(status="NO_SHOW").count()
        return Response(
            {
                "total": qs.count(),
                "futuros": futuro.count(),
                "confirmados_futuros": futuro.filter(status="CONFIRMADO").count(),
                "pendentes_futuros": futuro.filter(status="PENDENTE").count(),
                "no_show_total": no_show,
            },
        )

    @action(detail=False, methods=["get"])
    def capacidade(self, request: Request) -> Response:
        """Capacidade agregada por profissional e data."""
        tenant = get_current_tenant(request._request)  # noqa: SLF001
        data_start = request.query_params.get("data_start")
        data_end = request.query_params.get("data_end")
        qs = Slot.objects.filter(tenant=tenant, ativo=True)
        if data_start:
            qs = qs.filter(horario__date__gte=data_start)
        if data_end:
            qs = qs.filter(horario__date__lte=data_end)
        agg = qs.values("profissional_id").annotate(
            slots=Count("id"),
            capacidade_total=Sum("capacidade_total"),
            capacidade_utilizada=Sum("capacidade_utilizada"),
        )
        return Response(list(agg))

    def perform_create(self, serializer: drf_serializers.Serializer) -> None:
        """Cria um agendamento usando o AgendamentoService."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        user = self.request.user
        if not tenant:
            msg = "Tenant inválido"
            raise permissions.PermissionDenied(msg)
        if not isinstance(user, AbstractUser):
            msg = "Usuário inválido"
            raise permissions.PermissionDenied(msg)

        validated_data = serializer.validated_data
        if not validated_data:
            msg = "Dados de validação não encontrados."
            raise drf_serializers.ValidationError(msg)

        slot = validated_data.get("slot")
        data_inicio = validated_data.get("data_inicio")
        data_fim = validated_data.get("data_fim")
        if not slot and (not data_inicio or not data_fim):
            msg = "Para agendamento manual informe data_inicio e data_fim"
            raise permissions.PermissionDenied(msg)

        if not data_inicio:
            msg = "Data de início é obrigatória"
            raise drf_serializers.ValidationError(msg)

        metadata = validated_data.get("metadata") or {}
        if not slot:
            metadata.setdefault("manual_sem_slot", True)

        try:
            with transaction.atomic():
                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=validated_data.get("cliente"),
                    profissional=validated_data.get("profissional") or (slot.profissional if slot else user),
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem=validated_data.get("origem") or ("PROFISSIONAL" if user.is_staff else "CLIENTE"),
                    slot=slot,
                    servico=self.request.data.get("servico_id"),
                    metadata=metadata,
                    user=user,
                )
        except (ValueError, TypeError) as e:
            raise drf_serializers.ValidationError({"detail": str(e)}) from e
        serializer.instance = ag

    def create(self, request: Request, *args: tuple, **kwargs: dict) -> Response:
        """Cria um agendamento e retorna os dados detalhados."""
        return super().create(request, *args, **kwargs)


class ClienteSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """Listagem de slots para clientes (portal).

    Suporta filtro por serviço e aplica competência do profissional quando flag ativa.
    """

    queryset = Slot.objects.select_related("profissional", "disponibilidade").all()
    serializer_class = SlotSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [
        permissions.IsAuthenticated,
        IsClientePortal,
    ]

    def get_queryset(self) -> QuerySet[Slot]:
        """Filtra slots disponíveis para o cliente."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        now = timezone.now()
        qs = Slot.objects.filter(tenant=tenant, ativo=True, horario__gte=now).select_related(
            "profissional",
            "disponibilidade",
        )
        qs = qs.filter(capacidade_utilizada__lt=F("capacidade_total"))  # somente com vaga

        profissional_id = self.request.query_params.get("profissional")
        data = self.request.query_params.get("data")
        servico_id = self.request.query_params.get("servico") or self.request.query_params.get("servico_id")

        if profissional_id:
            qs = qs.filter(profissional_id=profissional_id)
        if data:
            qs = qs.filter(horario__date=data)
        if servico_id and tenant and getattr(dj_settings, "ENFORCE_COMPETENCIA", False):
            with contextlib.suppress(Exception):
                profissionais_competentes = ProfissionalProcedimento.objects.filter(
                    tenant=tenant,
                    servico_id=servico_id,
                    ativo=True,
                ).values_list("profissional_id", flat=True)
                qs = qs.filter(profissional_id__in=profissionais_competentes)

        cache_key = (
            f"ag:slots_cli:{tenant.id if tenant else '-'}:{profissional_id or '-'}:{data or '-'}:"
            f"{servico_id or '-'}:{get_slots_cache_version()}"
        )
        if cached_ids := cache.get(cache_key):
            return qs.filter(id__in=cached_ids).order_by("horario", "id")

        ordered = qs.order_by("horario", "id")
        with contextlib.suppress(Exception):
            cache.set(cache_key, list(ordered.values_list("id", flat=True)), 20)
        return ordered

    @action(detail=True, methods=["post"])
    def reservar(self, request: Request, pk: str | None = None) -> Response:
        """Cliente reserva um slot: cliente é inferido do vínculo do portal."""
        del pk
        slot = self.get_object()
        if not hasattr(request, "session"):
            request.session = {}
        if "tenant_id" not in request.session and slot.tenant_id:
            request.session["tenant_id"] = slot.tenant_id

        cliente = _resolver_cliente_do_usuario(request)
        if not cliente:
            msg = "Acesso de cliente não encontrado para este tenant"
            return Response({"detail": msg}, status=status.HTTP_403_FORBIDDEN)

        servico_id = request.data.get("servico_id")
        if servico_id:
            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico_id)
                # Regra: cliente portal deve receber 403 quando serviço clínico não permitido (ex: offline/inativo)
                if _serv.is_clinical and not can_schedule_clinical_service(request.user, _serv):
                    return Response(
                        {"detail": str(CLINICAL_SCHEDULING_DENIED_MESSAGE)},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except _Servico.DoesNotExist:
                msg = "Serviço inválido"
                return Response({"detail": _(msg)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ag = AgendamentoService.criar(
                tenant=slot.tenant,
                cliente=cliente,
                profissional=slot.profissional,
                data_inicio=slot.horario,
                data_fim=None,
                origem="CLIENTE",
                slot=slot,
                servico=servico_id,
                metadata={"portal_cliente": True},
                user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ser = AgendamentoSerializer(ag)
        return Response({"slot": slot.id, "agendamento": ser.data})


class ClienteAgendamentoViewSet(viewsets.ModelViewSet):
    """Agendamentos do cliente (portal).

    Lista e cria para o Cliente associado ao usuário.
    Ações de cancelar/reagendar disponíveis com regras de negócio do serviço.
    """

    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [
        permissions.IsAuthenticated,
        IsClientePortal,
    ]

    def get_queryset(self) -> QuerySet[Agendamento]:
        """Filtra agendamentos para o cliente do usuário logado."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        cliente = _resolver_cliente_do_usuario(Request(self.request))
        if not tenant or not cliente:
            return Agendamento.objects.none()

        qs = Agendamento.objects.filter(tenant=tenant, cliente=cliente)
        # Filtros opcionais
        status_f = self.request.query_params.get("status")
        dstart = self.request.query_params.get("data_start")
        dend = self.request.query_params.get("data_end")
        if status_f:
            qs = qs.filter(status=status_f)
        if dstart:
            qs = qs.filter(data_inicio__date__gte=dstart)
        if dend:
            qs = qs.filter(data_fim__date__lte=dend)
        return qs.order_by("data_inicio", "id")

    def _validate_agendamento_data_cliente(self, validated_data: dict, user: AbstractUser) -> None:
        """Valida os dados para criação de agendamento pelo cliente."""
        slot = validated_data.get("slot")
        data_inicio = validated_data.get("data_inicio")
        data_fim = validated_data.get("data_fim")

        if not slot and (not data_inicio or not data_fim):
            msg = "Informe slot ou data_inicio/data_fim"
            raise permissions.PermissionDenied(msg)

        profissional = validated_data.get("profissional")
        if not profissional and slot:
            profissional = slot.profissional

        if not profissional:
            msg = "Profissional obrigatório"
            raise permissions.PermissionDenied(msg)

        servico = self.request.data.get("servico_id")
        if servico:
            try:
                _serv = _Servico.objects.select_related("perfil_clinico").get(id=servico)
                if _serv.is_clinical and isinstance(user, User) and not can_schedule_clinical_service(user, _serv):
                    raise permissions.PermissionDenied(str(CLINICAL_SCHEDULING_DENIED_MESSAGE))
            except _Servico.DoesNotExist as e:
                msg = "Serviço inválido"
                raise permissions.PermissionDenied(msg) from e

    def perform_create(self, serializer: drf_serializers.Serializer) -> None:
        """Cria um agendamento para o cliente do portal."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        user = self.request.user
        cliente = _resolver_cliente_do_usuario(Request(self.request))
        if not tenant or not cliente:
            msg = "Acesso de cliente não encontrado para este tenant"
            raise permissions.PermissionDenied(msg)
        if not isinstance(user, AbstractUser):
            msg = "Usuário inválido"
            raise permissions.PermissionDenied(msg)

        validated_data = serializer.validated_data
        if not isinstance(validated_data, dict):
            msg = "Dados de validação inválidos."
            raise drf_serializers.ValidationError(msg)

        self._validate_agendamento_data_cliente(validated_data, user)

        slot = validated_data.get("slot")
        data_inicio = validated_data.get("data_inicio")
        data_fim = validated_data.get("data_fim")
        profissional = validated_data.get("profissional")
        if not profissional and slot:
            profissional = slot.profissional

        servico = self.request.data.get("servico_id")
        metadata = validated_data.get("metadata")

        if not data_inicio:
            msg = "Data de início é obrigatória."
            raise drf_serializers.ValidationError(msg)

        try:
            with transaction.atomic():
                ag = AgendamentoService.criar(
                    tenant=tenant,
                    cliente=cliente,
                    profissional=profissional,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem="CLIENTE",
                    slot=slot,
                    servico=servico,
                    metadata={**(metadata or {}), "portal_cliente": True},
                    user=user,
                )
        except (ValueError, TypeError) as e:
            raise drf_serializers.ValidationError({"detail": str(e)}) from e
        serializer.instance = ag

    @action(detail=True, methods=["post"])
    def cancelar(self, request: Request, pk: str | None = None) -> Response:
        """Cancela um agendamento do cliente."""
        del pk
        ag = self.get_object()
        motivo = request.data.get("motivo") or "Cancelado pelo Cliente"
        try:
            AgendamentoService.cancelar(ag, motivo=motivo, user=request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok", "novo_status": ag.status})

    @action(detail=True, methods=["post"])
    def reagendar(self, request: Request, pk: str | None = None) -> Response:
        """Reagenda um agendamento do cliente."""
        del pk
        ag = self.get_object()
        novo_slot_id = request.data.get("novo_slot")
        nova_data_inicio_str = request.data.get("nova_data_inicio")
        nova_data_fim_str = request.data.get("nova_data_fim")
        motivo = request.data.get("motivo") or "Reagendamento pelo Cliente"

        novo_slot = None
        if novo_slot_id:
            novo_slot = Slot.objects.filter(id=novo_slot_id, tenant=ag.tenant, ativo=True).first()
            if not novo_slot:
                return Response({"detail": "novo_slot inválido"}, status=status.HTTP_400_BAD_REQUEST)

        nova_data_inicio = parse_datetime(nova_data_inicio_str) if nova_data_inicio_str else None
        nova_data_fim = parse_datetime(nova_data_fim_str) if nova_data_fim_str else None

        try:
            novo = AgendamentoService.reagendar(
                ag,
                novo_slot=novo_slot,
                nova_data_inicio=nova_data_inicio,
                nova_data_fim=nova_data_fim,
                user=request.user,
                motivo=motivo,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ser = self.get_serializer(novo)
        return Response(ser.data)


class AuditoriaAgendamentoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para visualização da auditoria de agendamentos."""

    queryset = AuditoriaAgendamento.objects.select_related("agendamento", "user").all()
    serializer_class = AuditoriaAgendamentoSerializer
    permission_classes: ClassVar[list[type[permissions.BasePermission]]] = [IsAgendamentoAuditoria]

    def get_queryset(self) -> QuerySet[AuditoriaAgendamento]:
        """Filtra a auditoria para o tenant atual."""
        tenant = get_current_tenant(self.request._request)  # noqa: SLF001
        return self.queryset.filter(agendamento__tenant=tenant)

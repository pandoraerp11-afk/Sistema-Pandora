"""Decorators reutilizáveis para portais (fornecedor e cliente)."""

from collections.abc import Callable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse

from portal_cliente.models import ContaCliente
from portal_fornecedor.models import AcessoFornecedor


def fornecedor_required(func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Exigir acesso fornecedor ativo ou retornar 404."""

    @login_required
    @wraps(func)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        try:
            acesso = AcessoFornecedor.objects.select_related("fornecedor").get(usuario=request.user, ativo=True)
        except AcessoFornecedor.DoesNotExist as exc:  # pragma: no cover - fluxo negativo
            msg = "Fornecedor sem acesso ativo"
            raise Http404(msg) from exc
        request.acesso_fornecedor = acesso
        return func(request, *args, **kwargs)

    return wrapper


def cliente_portal_required(func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Exigir contas cliente ativas ou retornar 404."""

    @login_required
    @wraps(func)
    def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        contas = ContaCliente.objects.filter(usuario=request.user, ativo=True).select_related("cliente")
        if not contas.exists():  # pragma: no cover - cenário negativo simples
            msg = "Nenhuma conta cliente ativa"
            raise Http404(msg)
        if "tenant_id" not in request.session:
            first = contas.first()
            if first and getattr(first.cliente, "tenant_id", None):
                request.session["tenant_id"] = first.cliente.tenant_id
        request.contas_cliente = list(contas)
        return func(request, *args, **kwargs)

    return wrapper

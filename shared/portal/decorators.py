"""Decorators reutilizáveis para portais (fornecedor e cliente)."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404

from portal_cliente.models import ContaCliente
from portal_fornecedor.models import AcessoFornecedor


def fornecedor_required(func):
    @login_required
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            acesso = AcessoFornecedor.objects.select_related("fornecedor").get(usuario=request.user, ativo=True)
        except AcessoFornecedor.DoesNotExist:
            raise Http404("Acesso fornecedor não encontrado")
        request.acesso_fornecedor = acesso
        return func(request, *args, **kwargs)

    return wrapper


def cliente_portal_required(func):
    @login_required
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        contas = ContaCliente.objects.filter(usuario=request.user, ativo=True).select_related("cliente")
        if not contas.exists():
            raise Http404("Nenhuma conta cliente ativa")
        # Se o tenant ainda não estiver na sessão (usuário portal puro), tenta definir a partir da primeira conta
        if "tenant_id" not in request.session:
            first = contas.first()
            if first and getattr(first.cliente, "tenant_id", None):
                request.session["tenant_id"] = first.cliente.tenant_id
        request.contas_cliente = list(contas)
        return func(request, *args, **kwargs)

    return wrapper

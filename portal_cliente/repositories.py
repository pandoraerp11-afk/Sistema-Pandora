"""Repositories / data access helpers para Portal Cliente.

Centraliza querysets reutilizados para reduzir risco de regressões.
"""

from django.db.models import QuerySet

from prontuarios.models import FotoEvolucao


class FotoEvolucaoRepository:
    """Acesso consolidado a FotoEvolucao para o portal.

    Critérios de exposição (fase atual):
    - Vinculada ao tenant e cliente da conta
    - Marcada como visível ao cliente (visivel_cliente=True)
    - Possui thumbnail gerada (imagem_thumbnail not null e != '')
    - (Futuro) Apenas mídias aprovadas e com derivados completos
    """

    @staticmethod
    def portal_queryset(tenant, cliente) -> QuerySet:
        return FotoEvolucao.objects.filter(
            tenant=tenant,
            cliente=cliente,
            visivel_cliente=True,
            imagem_thumbnail__isnull=False,
        ).exclude(imagem_thumbnail="")

    @staticmethod
    def recentes(tenant, cliente, limit: int = 6) -> QuerySet:
        return FotoEvolucaoRepository.portal_queryset(tenant, cliente).order_by("-created_at")[:limit]

    @staticmethod
    def do_atendimento(atendimento) -> QuerySet:
        return (
            FotoEvolucaoRepository.portal_queryset(atendimento.tenant, atendimento.cliente)
            .filter(atendimento=atendimento)
            .order_by("created_at")
        )

    @staticmethod
    def paginadas(tenant, cliente) -> QuerySet:
        # Ordenação padrão mais recente primeiro
        return (
            FotoEvolucaoRepository.portal_queryset(tenant, cliente)
            .select_related("atendimento__servico")
            .order_by("-created_at")
        )

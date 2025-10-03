"""Serviços utilitários do módulo de Documentos.

Inclui funções de resolução de exigências (regras) e consolidação de
uploads temporários do wizard para modelos persistentes.
"""

import contextlib
import logging
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Max

from core.models import Tenant

from .models import Documento, DocumentoVersao, RegraDocumento, TipoDocumento, WizardTenantDocumentoTemp

logger = logging.getLogger(__name__)


def resolver_exigencias_tenant(
    tenant_id: int | None = None,
    tipos: Iterable[TipoDocumento] | None = None,
) -> dict[int, str]:
    """Retorna dict {tipo_id: exigencia} considerando regras aprovadas.

    Prioridade: regra tenant > regra plataforma (escopo app) > default opcional.
    """
    if tipos is None:
        tipos = TipoDocumento.objects.filter(ativo=True)
    tipo_ids = [t.id for t in tipos]
    result = dict.fromkeys(tipo_ids, "opcional")  # base
    plataformas = RegraDocumento.objects.filter(
        status="aprovada",
        ativo=True,
        escopo="app",
        tipo_id__in=tipo_ids,
    ).only("tipo_id", "exigencia")
    for r in plataformas:
        result[r.tipo_id] = r.exigencia
    if tenant_id:
        tenants = RegraDocumento.objects.filter(
            status="aprovada",
            ativo=True,
            escopo="tenant",
            tenant_id=tenant_id,
            tipo_id__in=tipo_ids,
        ).only("tipo_id", "exigencia")
        for r in tenants:
            result[r.tipo_id] = r.exigencia
    return result


def resolver_exigencias_context(
    tenant_id: int | None = None,
    entity_ct: ContentType | None = None,
    entity_id: int | None = None,
    tipos: Iterable[TipoDocumento] | None = None,
) -> dict[int, str]:
    """Resolve exigências considerando camadas adicionais (entidade específica).

    Prioridade (maior para menor):
        1. Regra escopo="entidade" (content type + object id) -> sobrescreve tudo
        2. Regra escopo="tenant" -> sobrescreve app
        3. Regra escopo="app" -> sobrescreve default
        4. Default = opcional

    (Futuro) Escopo "filtro" pode ser inserido entre entidade e tenant, dependendo da semântica.
    Mantido separado de `resolver_exigencias_tenant` para clareza e retrocompatibilidade.
    """
    if tipos is None:
        tipos = TipoDocumento.objects.filter(ativo=True)
    tipo_ids = [t.id for t in tipos]
    result = dict.fromkeys(tipo_ids, "opcional")

    # Nivel app
    for r in RegraDocumento.objects.filter(
        status="aprovada",
        ativo=True,
        escopo="app",
        tipo_id__in=tipo_ids,
    ).only("tipo_id", "exigencia"):
        result[r.tipo_id] = r.exigencia

    # Nivel tenant
    if tenant_id:
        for r in RegraDocumento.objects.filter(
            status="aprovada",
            ativo=True,
            escopo="tenant",
            tenant_id=tenant_id,
            tipo_id__in=tipo_ids,
        ).only("tipo_id", "exigencia"):
            result[r.tipo_id] = r.exigencia

    # Nivel entidade específica
    if entity_ct and entity_id:
        for r in RegraDocumento.objects.filter(
            status="aprovada",
            ativo=True,
            escopo="entidade",
            entidade_content_type=entity_ct,
            entidade_object_id=entity_id,
            tipo_id__in=tipo_ids,
        ).only("tipo_id", "exigencia"):
            result[r.tipo_id] = r.exigencia

    return result


def _get_or_create_documento(
    tenant: Tenant,
    ct_tenant: ContentType,
    temp: WizardTenantDocumentoTemp,
) -> tuple[Documento, bool]:
    """Cria ou retorna Documento base para o temp."""
    tipo = temp.tipo
    return Documento.objects.get_or_create(
        entidade_content_type=ct_tenant,
        entidade_object_id=tenant.id,
        tipo=tipo,
        defaults={
            "periodicidade_aplicada": tipo.periodicidade,
            "obrigatorio": bool(temp.obrigatorio_snapshot),
        },
    )


def _atualiza_documento_se_preciso(doc: Documento, temp: WizardTenantDocumentoTemp) -> None:
    tipo = temp.tipo
    changed = False
    if doc.periodicidade_aplicada != tipo.periodicidade:
        doc.periodicidade_aplicada = tipo.periodicidade
        changed = True
    obrig = bool(temp.obrigatorio_snapshot)
    if doc.obrigatorio != obrig:
        doc.obrigatorio = obrig
        changed = True
    if changed:
        doc.save(update_fields=["periodicidade_aplicada", "obrigatorio", "atualizado_em"])


@runtime_checkable
class _UserLike(Protocol):  # mínimo necessário
    pk: int | None


def _cria_versao(doc: Documento, temp: WizardTenantDocumentoTemp, tenant: Tenant, user: _UserLike | None) -> bool:
    try:
        with temp.arquivo.open("rb") as fh:
            content = fh.read()
    except OSError as exc:
        logger.warning("Falha IO leitura temp_id=%s: %s", temp.id, exc)
        return False
    else:
        try:
            next_versao = (doc.versoes.aggregate(Max("versao")).get("versao__max") or 0) + 1
            new_name = f"tenant_{tenant.id}_tipo_{temp.tipo.id}_{temp.filename_original}"
            DocumentoVersao.objects.create(
                documento=doc,
                arquivo=ContentFile(content, name=new_name),
                enviado_por=user if getattr(user, "pk", None) else None,
                versao=next_versao,
                status="pendente",
            )
        except (OSError, ValueError, RuntimeError) as exc:
            logger.warning("Falha ao persistir versão temp_id=%s: %s", temp.id, exc)
            return False
        else:
            return True


def _remover_temp(temp: WizardTenantDocumentoTemp) -> bool:
    with contextlib.suppress(Exception):
        temp.arquivo.delete(save=False)
    try:
        temp.delete()
    except (OSError, RuntimeError) as exc:
        logger.warning("Falha ao remover temp_id=%s: %s", temp.id, exc)
        return False
    return True


def consolidate_wizard_temp_to_documents(
    tenant: Tenant,
    session_key: str | None = None,
    user: _UserLike | None = None,
) -> dict[str, int]:
    """Consolida uploads temporários do wizard para o módulo Documentos.

    Retorna contadores: processados, criados_documentos, criadas_versoes, removidos_temp.
    """
    if not isinstance(tenant, Tenant):  # validação defensiva
        return {"processados": 0, "criados_documentos": 0, "criadas_versoes": 0, "removidos_temp": 0}

    ct_tenant = ContentType.objects.get_for_model(Tenant)
    qs = WizardTenantDocumentoTemp.objects.filter(tenant=tenant)
    if session_key:  # anexar uploads feitos antes de amarrar o tenant
        qs = WizardTenantDocumentoTemp.objects.filter(tenant__isnull=True, session_key=session_key) | qs

    stats = {"processados": 0, "criados_documentos": 0, "criadas_versoes": 0, "removidos_temp": 0}

    for temp in qs.select_related("tipo").order_by("id"):
        stats["processados"] += 1
        doc, created = _get_or_create_documento(tenant, ct_tenant, temp)
        if created:
            stats["criados_documentos"] += 1
        else:
            _atualiza_documento_se_preciso(doc, temp)
        if _cria_versao(doc, temp, tenant, user):  # versão criada
            stats["criadas_versoes"] += 1
        if _remover_temp(temp):
            stats["removidos_temp"] += 1

    return stats

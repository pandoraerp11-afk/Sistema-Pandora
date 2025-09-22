import contextlib
from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Max

from core.models import Tenant

from .models import Documento, DocumentoVersao, RegraDocumento, TipoDocumento, WizardTenantDocumentoTemp


def resolver_exigencias_tenant(tenant_id=None, tipos: Iterable[TipoDocumento] = None) -> dict[int, str]:
    """Retorna dict {tipo_id: exigencia} considerando regras aprovadas.
    Prioridade: regra tenant > regra plataforma (escopo app) > default opcional.
    """
    if tipos is None:
        tipos = TipoDocumento.objects.filter(ativo=True)
    tipo_ids = [t.id for t in tipos]
    result = {tid: "opcional" for tid in tipo_ids}
    plataformas = RegraDocumento.objects.filter(
        status="aprovada", ativo=True, escopo="app", tipo_id__in=tipo_ids
    ).select_related("tipo")
    for r in plataformas:
        result[r.tipo_id] = r.exigencia
    if tenant_id:
        tenants = RegraDocumento.objects.filter(
            status="aprovada", ativo=True, escopo="tenant", tenant_id=tenant_id, tipo_id__in=tipo_ids
        ).select_related("tipo")
        for r in tenants:
            result[r.tipo_id] = r.exigencia
    return result


def consolidate_wizard_temp_to_documents(tenant: Tenant, session_key: str | None = None, user=None) -> dict[str, int]:
    """Consolida uploads temporários do wizard para o módulo Documentos.

    - Converte registros em `WizardTenantDocumentoTemp` em `Documento` + `DocumentoVersao`.
    - Usa o próprio `Tenant` como entidade alvo (GenericForeignKey via ContentType).
    - Define `obrigatorio` a partir do snapshot temporário; `periodicidade_aplicada` herdada do tipo.

    Retorna: { 'processados': X, 'criados_documentos': Y, 'criadas_versoes': Z, 'removidos_temp': W }
    """
    if not tenant or not isinstance(tenant, Tenant):
        return {"processados": 0, "criados_documentos": 0, "criadas_versoes": 0, "removidos_temp": 0}

    ct_tenant = ContentType.objects.get_for_model(Tenant)

    qs = WizardTenantDocumentoTemp.objects.filter(tenant=tenant)
    # Em fluxo de criação, arquivos podem estar vinculados por session_key
    if session_key:
        qs = WizardTenantDocumentoTemp.objects.filter(tenant__isnull=True, session_key=session_key) | qs

    processados = 0
    criados_documentos = 0
    criadas_versoes = 0
    removidos_temp = 0

    # Consolidar cada temp para Documento/Versão
    for temp in qs.select_related("tipo").order_by("id"):
        processados += 1
        tipo = temp.tipo
        # Documento por (Tenant, Tipo)
        doc, created = Documento.objects.get_or_create(
            entidade_content_type=ct_tenant,
            entidade_object_id=tenant.id,
            tipo=tipo,
            defaults={
                "periodicidade_aplicada": tipo.periodicidade,
                "obrigatorio": bool(temp.obrigatorio_snapshot),
            },
        )
        if created:
            criados_documentos += 1
        else:
            # Atualizar flags que podem ter mudado
            changed = False
            if doc.periodicidade_aplicada != tipo.periodicidade:
                doc.periodicidade_aplicada = tipo.periodicidade
                changed = True
            if doc.obrigatorio != bool(temp.obrigatorio_snapshot):
                doc.obrigatorio = bool(temp.obrigatorio_snapshot)
                changed = True
            if changed:
                doc.save(update_fields=["periodicidade_aplicada", "obrigatorio", "atualizado_em"])

        # Criar nova versão a partir do arquivo temp
        try:
            with temp.arquivo.open("rb") as fh:
                content = fh.read()
            next_versao = (doc.versoes.aggregate(Max("versao")).get("versao__max") or 0) + 1
            new_name = f"tenant_{tenant.id}_tipo_{tipo.id}_{temp.filename_original}"
            DocumentoVersao.objects.create(
                documento=doc,
                arquivo=ContentFile(content, name=new_name),
                enviado_por=getattr(user, "pk", None) and user or None,
                versao=next_versao,
                status="pendente",
            )
            criadas_versoes += 1
        except Exception:
            # Continua com cleanup mesmo em caso de falha de versão
            pass

        # Cleanup do temp (arquivo + registro)
        try:
            with contextlib.suppress(Exception):
                temp.arquivo.delete(save=False)
            temp.delete()
            removidos_temp += 1
        except Exception:
            pass

    return {
        "processados": processados,
        "criados_documentos": criados_documentos,
        "criadas_versoes": criadas_versoes,
        "removidos_temp": removidos_temp,
    }

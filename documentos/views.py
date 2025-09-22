from django.contrib.auth.decorators import login_required
from django.db.models import Q

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions


@login_required
def documento_home(request):
    total_tipos = TipoDocumento.objects.count()
    total_categorias = CategoriaDocumento.objects.count()
    total_documentos = Documento.objects.count()
    total_versoes = DocumentoVersao.objects.count()
    # Regras recentes combinando globais + do tenant corrente (se existir)
    tenant_id = getattr(getattr(request, "tenant", None), "id", None)
    base_qs = RegraDocumento.objects.filter(status="aprovada").select_related("tipo", "entidade_content_type")
    if tenant_id:
        recent_regras = base_qs.filter(
            Q(escopo="app", tenant__isnull=True) | Q(escopo="tenant", tenant_id=tenant_id)
        ).order_by("-atualizado_em")[:8]
    else:
        recent_regras = base_qs.filter(tenant__isnull=True).order_by("-atualizado_em")[:8]
    from django.db.models import Count

    exigencia_stats_qs = RegraDocumento.objects.values("exigencia").annotate(qtd=Count("id"))
    exigencia_stats = {item["exigencia"]: item["qtd"] for item in exigencia_stats_qs}
    total_exig = sum(exigencia_stats.values()) or 0

    def pct(v):
        return int(round((v / total_exig) * 100)) if total_exig else 0

    exigencia_percent = {
        "obrigatorio": pct(exigencia_stats.get("obrigatorio", 0)),
        "recomendado": pct(exigencia_stats.get("recomendado", 0)),
        "opcional": pct(exigencia_stats.get("opcional", 0)),
    }
    context = {
        "total_tipos": total_tipos,
        "total_categorias": total_categorias,
        "total_documentos": total_documentos,
        "total_versoes": total_versoes,
        "recent_regras": recent_regras,
        "exigencia_stats": exigencia_stats,
        "exigencia_percent": exigencia_percent,
        "categorias_options": list(CategoriaDocumento.objects.order_by("nome").values("id", "nome")),
        "periodicidade_choices": TipoDocumento.PERIODICIDADE_CHOICES,
        "tipos_options": list(
            TipoDocumento.objects.select_related("categoria").order_by("nome").values("id", "nome", "categoria__nome")
        ),
        "dominios_options": list(
            DominioDocumento.objects.filter(ativo=True).order_by("nome").values("id", "nome", "slug", "app_label")
        ),
        "exigencia_choices": RegraDocumento.EXIGENCIA_CHOICES,
    }
    return render(request, "documentos/documentos_home.html", context)


import json

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import (
    CategoriaDocumentoForm,
    DocumentoForm,
    DocumentoVersaoForm,
    DominioDocumentoForm,
    RegraDocumentoForm,
    TipoDocumentoForm,
)
from .models import (
    CategoriaDocumento,
    Documento,
    DocumentoVersao,
    DominioDocumento,
    RegraDocumento,
    TipoDocumento,
    WizardTenantDocumentoTemp,
)
from .services import resolver_exigencias_tenant


def _get_content_type_or_404(app_label, object_id=None, model_hint=None):
    """Resolve o ContentType correto para um app_label.
    Caso existam múltiplos models, tenta:
      1. Filtrar por model_hint (se fornecido)
      2. Tentar carregar o object_id em cada ContentType do app_label (primeiro que existir)
      3. Heurísticas por nome
      4. Fallback: primeiro
    """
    qs = ContentType.objects.filter(app_label=app_label)
    if not qs.exists():
        raise Http404(f"ContentType não encontrado para app_label={app_label}")
    if model_hint:
        mh_qs = qs.filter(model=model_hint.lower())
        if mh_qs.exists():
            qs = mh_qs
    # Se temos object_id e múltiplos, testar cada um
    if object_id is not None and qs.count() > 1:
        for ct in qs.order_by("id"):
            model_cls = ct.model_class()
            try:
                model_cls._base_manager.get(pk=object_id)
                return ct
            except model_cls.DoesNotExist:  # noqa
                continue
        # heurísticas se nenhum bateu
        heuristicas = ["fornecedor", app_label.rstrip("s")]
        for h in heuristicas:
            cand = qs.filter(model__icontains=h).first()
            if cand:
                return cand
        return qs.order_by("id").first()
    # único ou sem object test
    return qs.first()


def categoria_list(request):
    qs = CategoriaDocumento.objects.all().order_by("ordem", "nome")
    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, app_label="documentos", model_name="categoriadocumento")
    context = {
        "object_list": qs,
        "page_title": _("Categorias de Documento"),
        "page_subtitle": _("Gerencie as categorias para tipos de documentos"),
        "add_url": reverse("documentos:categoria_create"),
        "reorder_url": reverse("documentos:categoria_reorder"),
        "statistics": [
            {
                "value": qs.count(),
                "label": _("Total"),
                "icon": "fas fa-database",
                "bg": "bg-gradient-primary",
                "text_color": "text-primary",
            },
            {
                "value": qs.filter(ativo=True).count(),
                "label": _("Ativas"),
                "icon": "fas fa-check",
                "bg": "bg-gradient-success",
                "text_color": "text-success",
            },
            {
                "value": qs.filter(ativo=False).count(),
                "label": _("Inativas"),
                "icon": "fas fa-ban",
                "bg": "bg-gradient-secondary",
                "text_color": "text-secondary",
            },
        ],
        "table_columns": [
            {"label": _("Nome"), "field": "nome", "sortable": True},
            {"label": _("Descrição"), "field": "descricao"},
            {"label": _("Ativo"), "field": "ativo"},
            {"label": _("Ordem"), "field": "ordem", "sortable": True},
        ],
        # actions removido (template custom já renderiza botões);
        "ui_perms": ui_perms,
        "perms_ui": ui_perms,
    }
    return render(request, "documentos/categoria_list.html", context)


def categoria_create(request):
    form = CategoriaDocumentoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, _("Categoria criada com sucesso!"))
        return redirect("documentos:categoria_list")
    return render(request, "documentos/categoria_form.html", {"form": form})


@login_required
@require_POST
def categoria_create_ajax(request):
    """Cria categoria via AJAX retornando JSON.
    Request: POST form-urlencoded ou JSON {nome, descricao, ativo}
    Response sucesso: {ok:true, categoria:{id,nome,descricao,ativo,ordem}}
    Response erro: {ok:false, errors:{campo:[msgs]}}
    """
    data = request.POST or None
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
            data = payload
        except Exception:
            return JsonResponse({"ok": False, "errors": {"__all__": [_("JSON inválido")]}}, status=400)
    form = CategoriaDocumentoForm(data)
    if form.is_valid():
        # definir próxima ordem automaticamente (maior ordem + 1)
        try:
            max_ordem = CategoriaDocumento.objects.order_by("-ordem").values_list("ordem", flat=True).first() or 0
        except Exception:
            max_ordem = 0
        cat = form.save(commit=False)
        if not cat.ordem or cat.ordem == 0:
            cat.ordem = max_ordem + 1
        cat.save()
        return JsonResponse(
            {
                "ok": True,
                "categoria": {
                    "id": cat.id,
                    "nome": cat.nome,
                    "descricao": cat.descricao or "",
                    "ativo": cat.ativo,
                    "ordem": cat.ordem,
                },
            }
        )
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


def categoria_edit(request, pk):
    categoria = get_object_or_404(CategoriaDocumento, pk=pk)
    form = CategoriaDocumentoForm(request.POST or None, instance=categoria)
    if form.is_valid():
        form.save()
        messages.success(request, _("Categoria atualizada com sucesso!"))
        return redirect("documentos:categoria_list")
    return render(request, "documentos/categoria_form.html", {"form": form, "categoria": categoria})


@login_required
def categoria_delete(request, pk):
    categoria = get_object_or_404(CategoriaDocumento, pk=pk)
    if request.method == "POST":
        nome = categoria.nome
        categoria.delete()
        messages.success(request, _('Categoria "%(nome)s" excluída com sucesso!') % {"nome": nome})
        return redirect("documentos:categoria_list")
    return render(request, "documentos/categoria_confirm_delete.html", {"categoria": categoria})


@login_required
@require_POST
def categoria_reorder(request):
    """Recebe JSON: {"ids": [3,1,7,...]} e atualiza campo ordem na sequência."""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    ids = data.get("ids")
    if not isinstance(ids, list):
        return JsonResponse({"error": "Formato inválido"}, status=400)
    # Validar existência e aplicar ordem incremental começando em 1
    ordem = 1
    updated = 0
    for cid in ids:
        try:
            cat = CategoriaDocumento.objects.get(pk=cid)
        except CategoriaDocumento.DoesNotExist:
            continue
        if cat.ordem != ordem:
            cat.ordem = ordem
            cat.save(update_fields=["ordem"])
        ordem += 1
        updated += 1
    return JsonResponse({"status": "ok", "updated": updated})


def tipo_list(request):
    tipos = TipoDocumento.objects.select_related("categoria").all()
    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, app_label="documentos", model_name="tipodocumento")
    return render(
        request,
        "documentos/tipo_list.html",
        {
            "tipos": tipos,
            "ui_perms": ui_perms,
            "perms_ui": ui_perms,
        },
    )


def tipo_create(request):
    form = TipoDocumentoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, _("Tipo de documento criado com sucesso!"))
        return redirect("documentos:tipo_list")
    return render(request, "documentos/tipo_form.html", {"form": form})


@login_required
@require_POST
def tipo_create_ajax(request):
    """Cria TipoDocumento via AJAX.
    Request JSON: {nome, descricao, categoria_id, periodicidade, ativo, versionavel}
    Response sucesso: {ok:true, tipo:{id,nome,descricao,categoria_nome,periodicidade,periodicidade_label,ativo,versionavel}}
    """
    data = request.POST or None
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "errors": {"__all__": [_("JSON inválido")]}}, status=400)
    # Mapear categoria_id -> categoria
    if isinstance(data, dict) and "categoria_id" in data and "categoria" not in data:
        data = data.copy()
        data["categoria"] = data.pop("categoria_id")
    form = TipoDocumentoForm(data)
    if form.is_valid():
        tipo = form.save()
        return JsonResponse(
            {
                "ok": True,
                "tipo": {
                    "id": tipo.id,
                    "nome": tipo.nome,
                    "descricao": tipo.descricao or "",
                    "categoria_nome": tipo.categoria.nome,
                    "categoria_id": tipo.categoria_id,
                    "periodicidade": tipo.periodicidade,
                    "periodicidade_label": tipo.get_periodicidade_display(),
                    "ativo": tipo.ativo,
                    "versionavel": tipo.versionavel,
                },
            }
        )
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


def tipo_edit(request, pk):
    tipo = get_object_or_404(TipoDocumento, pk=pk)
    form = TipoDocumentoForm(request.POST or None, instance=tipo)
    if form.is_valid():
        form.save()
        messages.success(request, _("Tipo de documento atualizado com sucesso!"))
        return redirect("documentos:tipo_list")
    return render(request, "documentos/tipo_form.html", {"form": form, "tipo": tipo})


def documento_list(request, app_label, object_id):
    # Evita MultipleObjectsReturned selecionando o primeiro model que combine (assumindo convenção de único model principal por app)
    ct = _get_content_type_or_404(app_label, object_id=object_id)
    entidade = ct.get_object_for_this_type(pk=object_id)
    documentos = Documento.objects.filter(entidade_content_type=ct, entidade_object_id=object_id).select_related("tipo")
    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, app_label="documentos", model_name="documento")
    return render(
        request,
        "documentos/documento_list.html",
        {
            "entidade": entidade,
            "documentos": documentos,
            "ui_perms": ui_perms,
            "perms_ui": ui_perms,
        },
    )


def documento_create(request, app_label, object_id):
    ct = _get_content_type_or_404(app_label, object_id=object_id)
    entidade = ct.get_object_for_this_type(pk=object_id)
    form = DocumentoForm(request.POST or None)
    if form.is_valid():
        doc = form.save(commit=False)
        doc.entidade_content_type = ct
        doc.entidade_object_id = object_id
        # Se periodicidade_aplicada não definida, tenta derivar de regra existente
        if not doc.periodicidade_aplicada:
            regra = RegraDocumento.objects.filter(
                entidade_content_type=ct, entidade_object_id=object_id, tipo=doc.tipo, ativo=True
            ).first()
            if regra and regra.periodicidade_override:
                doc.periodicidade_aplicada = regra.periodicidade_override
            else:
                doc.periodicidade_aplicada = doc.tipo.periodicidade
        # Ajusta obrigatoriedade conforme regra
        regra_obrig = RegraDocumento.objects.filter(
            entidade_content_type=ct, entidade_object_id=object_id, tipo=doc.tipo, ativo=True
        ).first()
        if regra_obrig:
            doc.obrigatorio = regra_obrig.exigencia == "obrigatorio"
        doc.save()
        messages.success(request, _("Documento associado com sucesso!"))
        return redirect("documentos:documento_list", app_label=app_label, object_id=object_id)
    return render(request, "documentos/documento_form.html", {"form": form, "entidade": entidade})


def regra_list(request, app_label, object_id):
    ct = _get_content_type_or_404(app_label, object_id=object_id)
    entidade = ct.get_object_for_this_type(pk=object_id)
    regras = RegraDocumento.objects.filter(entidade_content_type=ct, entidade_object_id=object_id).select_related(
        "tipo"
    )
    return render(
        request,
        "documentos/regra_list.html",
        {
            "entidade": entidade,
            "entidade_app_label": ct.app_label,
            "regras": regras,
        },
    )


def regra_create(request, app_label, object_id):
    ct = _get_content_type_or_404(app_label, object_id=object_id)
    entidade = ct.get_object_for_this_type(pk=object_id)
    form = RegraDocumentoForm(request.POST or None)
    if form.is_valid():
        regra = form.save(commit=False)
        # Configuração do escopo
        escopo = form.cleaned_data.get("escopo")
        regra.app_label = form.cleaned_data.get("app_label") or app_label
        if escopo == "entidade":
            regra.entidade_content_type = ct
            regra.entidade_object_id = object_id
        elif escopo in {"app", "filtro"}:
            regra.entidade_content_type = None
            regra.entidade_object_id = None
            regra.app_label = form.cleaned_data.get("app_label") or app_label
        regra.save()
        messages.success(request, _("Regra criada com sucesso!"))
        return redirect("documentos:regra_list", app_label=app_label, object_id=object_id)
    return render(
        request,
        "documentos/regra_form.html",
        {
            "form": form,
            "entidade": entidade,
            "entidade_app_label": ct.app_label,
            "page_title": _("Nova Regra de Documento"),
            "page_subtitle": _("Defina escopo, exigência e periodicidade"),
        },
    )


@login_required
def regra_create_global(request):
    """Cria uma regra em escopo global (app ou filtro), acessível a partir da home.
    Regras de escopo 'entidade' devem ser criadas na página da própria entidade.
    """
    form = RegraDocumentoForm(request.POST or None)
    if form.is_valid():
        regra = form.save(commit=False)
        escopo = form.cleaned_data.get("escopo")
        app_label = form.cleaned_data.get("app_label")
        # Escopos sem entidade
        if escopo in ("app", "filtro"):
            if not app_label:
                messages.error(request, _("Informe o App Label para regras globais (ex.: fornecedores)."))
            else:
                regra.entidade_content_type = None
                regra.entidade_object_id = None
                regra.save()
                messages.success(request, _("Regra global criada com sucesso!"))
                return redirect("documentos:documentos_home")
        # Escopo entidade: requer app_label e ID da entidade (com opção de model_hint)
        elif escopo == "entidade":
            ent_id = request.POST.get("entidade_object_id")
            model_hint = request.POST.get("model_hint") or None
            if not app_label or not ent_id:
                messages.error(request, _("Informe App Label e o ID da entidade."))
            else:
                try:
                    ct = _get_content_type_or_404(app_label, object_id=int(ent_id), model_hint=model_hint)
                    # valida existência do objeto
                    ct.get_object_for_this_type(pk=int(ent_id))
                    regra.entidade_content_type = ct
                    regra.entidade_object_id = int(ent_id)
                    regra.save()
                    messages.success(request, _("Regra criada para a entidade com sucesso!"))
                    return redirect("documentos:regra_list", app_label=ct.app_label, object_id=int(ent_id))
                except Exception as e:  # noqa
                    messages.error(
                        request, _("Não foi possível localizar a entidade informada. Verifique App Label, Modelo e ID.")
                    )
    # preparar sugestões de app_labels
    from django.contrib.contenttypes.models import ContentType

    app_labels = list(ContentType.objects.values_list("app_label", flat=True).distinct().order_by("app_label"))
    return render(
        request,
        "documentos/regra_form.html",
        {
            "form": form,
            "app_labels": app_labels,
            "page_title": _("Nova Regra de Documento"),
            "page_subtitle": _("Crie uma regra no escopo do app, filtro ou entidade específica"),
            # entidade_app_label ausente por ser global
        },
    )


def regra_edit(request, pk):
    regra = get_object_or_404(RegraDocumento, pk=pk)
    form = RegraDocumentoForm(request.POST or None, instance=regra)
    if form.is_valid():
        form.save()
        messages.success(request, _("Regra atualizada com sucesso!"))
        if regra.entidade_content_type and regra.entidade_object_id:
            return redirect(
                "documentos:regra_list",
                app_label=regra.entidade_content_type.app_label,
                object_id=regra.entidade_object_id,
            )
        return redirect("documentos:documentos_home")
    return render(
        request,
        "documentos/regra_form.html",
        {
            "form": form,
            "regra": regra,
            "entidade": regra.entidade if regra.entidade_content_type else None,
            "entidade_app_label": regra.entidade_content_type.app_label if regra.entidade_content_type else None,
            "page_title": _("Editar Regra de Documento"),
            "page_subtitle": _("Atualize escopo, exigência e periodicidade"),
        },
    )


def regra_delete(request, pk):
    regra = get_object_or_404(RegraDocumento, pk=pk)
    app_label = regra.entidade_content_type.app_label if regra.entidade_content_type else None
    object_id = regra.entidade_object_id if regra.entidade_object_id else None
    regra.delete()
    messages.success(request, _("Regra removida com sucesso!"))
    if app_label and object_id:
        return redirect("documentos:regra_list", app_label=app_label, object_id=object_id)
    return redirect("documentos:documentos_home")


@login_required
@require_POST
def regra_create_ajax(request):
    """Cria RegraDocumento via AJAX.
    Espera JSON ou form data com campos mínimos: tipo, exigencia, escopo ou nivel_aplicacao.
    Regras:
      - Determina escopo aplicando lógica similar às views existentes.
      - Para escopo entidade: requer app_label + entidade_object_id (+ opcional model_hint)
      - Para escopo app/filtro: app_label obrigatório.
    Retorno sucesso: {ok:true, regra:{id,tipo_id,tipo_nome,exigencia,exigencia_label,nivel_aplicacao,escopo,periodicidade,periodicidade_label,ativo,app_label}}
    Erro: {ok:false, errors:{campo:[msgs]}}
    """
    data = request.POST or None
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "errors": {"__all__": [_("JSON inválido")]}}, status=400)
    if not isinstance(data, dict):
        data = {}
    data = data.copy()
    # Normalizar nomes vindos do front (ex: tipo_id, entidade_id)
    if "tipo_id" in data and "tipo" not in data:
        data["tipo"] = data.pop("tipo_id")
    # Construção dinâmica de campos escopo
    escopo = data.get("escopo") or "app"
    dominio_id = data.get("dominio") or data.get("dominio_id")
    app_label = data.get("app_label") or data.get("appLabel")  # legado (pode vir de front antigo)
    entidade_object_id = data.get("entidade_object_id") or data.get("entidade_id") or data.get("object_id")
    model_hint = data.get("model_hint")

    # Validações manuais antes do form (para evitar erros pouco claros)
    preliminar_errors = {}
    if escopo in ("app", "filtro"):
        # Requer domínio (nova abordagem)
        if not dominio_id:
            preliminar_errors["dominio"] = [_("Selecione um domínio")]
        # Permissão: apenas superuser ou perm específica
        if not request.user.is_superuser and not request.user.has_perm("documentos.add_regra_global"):
            preliminar_errors["__all__"] = [_("Sem permissão para criar regra global")]
    if escopo == "tenant":
        # Apenas superuser ou tenant admin (simplificado aqui: superuser) pode criar.
        if not request.user.is_superuser:
            preliminar_errors["__all__"] = [_("Sem permissão para criar regra de tenant")]
    if escopo == "entidade" and not (app_label and entidade_object_id):
        preliminar_errors["__all__"] = [_("Informe app_label e entidade_object_id para escopo entidade")]
    if preliminar_errors:
        return JsonResponse({"ok": False, "errors": preliminar_errors}, status=400)

    # Força status conforme permissão
    if not request.user.is_superuser:
        data["status"] = "pendente"
    form = RegraDocumentoForm(data, user=request.user)
    if form.is_valid():
        regra = form.save(commit=False)
        escopo_clean = form.cleaned_data.get("escopo")
        # Aplicar mesma lógica da view tradicional
        if escopo_clean == "entidade":
            try:
                ct = _get_content_type_or_404(app_label, object_id=int(entidade_object_id), model_hint=model_hint)
                ct.get_object_for_this_type(pk=int(entidade_object_id))
                regra.entidade_content_type = ct
                regra.entidade_object_id = int(entidade_object_id)
            except Exception:
                return JsonResponse(
                    {
                        "ok": False,
                        "errors": {
                            "__all__": [_("Entidade não encontrada para app_label/model_hint/object_id informados")]
                        },
                    },
                    status=400,
                )
        elif escopo_clean == "tenant":
            # Bind tenant explicit ou derivado da sessão (se middleware define request.tenant)
            tenant_id = data.get("tenant") or getattr(getattr(request, "tenant", None), "id", None)
            if tenant_id:
                regra.tenant_id = tenant_id
            else:
                return JsonResponse({"ok": False, "errors": {"tenant": [_("Tenant não informado")]}}, status=400)
        else:
            regra.entidade_content_type = None
            regra.entidade_object_id = None
        # Auto-aprovação para superuser se não especificado
        if request.user.is_superuser and not regra.status:
            regra.status = "aprovada"
        regra.save()
        return JsonResponse(
            {
                "ok": True,
                "regra": {
                    "id": regra.id,
                    "tipo_id": regra.tipo_id,
                    "tipo_nome": regra.tipo.nome,
                    "exigencia": regra.exigencia,
                    "exigencia_label": regra.get_exigencia_display(),
                    "nivel_aplicacao": regra.nivel_aplicacao,
                    "escopo": regra.escopo,
                    "periodicidade_override": regra.periodicidade_override,
                    "periodicidade_label": regra.get_periodicidade_override_display()
                    if regra.periodicidade_override
                    else None,
                    "ativo": regra.ativo,
                    "status": regra.status,
                    "dominio_id": regra.dominio_id,
                },
            }
        )
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


def versao_list(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    versoes = documento.versoes.all()
    tenant = get_current_tenant(request)
    ui_perms = build_ui_permissions(request.user, tenant, app_label="documentos", model_name="documentoversao")
    return render(
        request,
        "documentos/versao_list.html",
        {
            "documento": documento,
            "versoes": versoes,
            "ui_perms": ui_perms,
            "perms_ui": ui_perms,
        },
    )


def versao_create(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    form = DocumentoVersaoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        from django.db.models import Max

        versao = form.save(commit=False)
        versao.documento = documento
        versao.versao = (documento.versoes.aggregate(Max("versao")).get("versao__max") or 0) + 1
        versao.save()
        messages.success(request, _("Nova versão enviada com sucesso!"))
        return redirect("documentos:versao_list", pk=pk)
    return render(request, "documentos/versao_form.html", {"form": form, "documento": documento})


# ===================== SETUP INTELIGENTE (UI) =====================
@login_required
def setup_inteligente(request):
    """Renderiza página única para criar categorias, tipos e regras em lote."""
    import json

    categorias_existentes = list(CategoriaDocumento.objects.values("id", "nome").order_by("nome"))
    tipos_existentes = list(TipoDocumento.objects.values("id", "nome", "categoria_id").order_by("nome"))
    # Garantir tipos básicos JSON (lista de listas)
    # Converter tuples (value, lazy_label) em listas simples com label forçada a str
    periodicidade_choices = [(v, str(lbl)) for v, lbl in TipoDocumento.PERIODICIDADE_CHOICES]
    exigencia_choices = [(v, str(lbl)) for v, lbl in RegraDocumento.EXIGENCIA_CHOICES]
    nivel_aplicacao_choices = [(v, str(lbl)) for v, lbl in RegraDocumento.NIVEL_APLICACAO_CHOICES]
    dominios_options = list(
        DominioDocumento.objects.filter(ativo=True).order_by("nome").values("id", "nome", "slug", "app_label")
    )
    context = {
        "categorias_existentes": json.dumps(categorias_existentes, ensure_ascii=False),
        "tipos_existentes": json.dumps(tipos_existentes, ensure_ascii=False),
        "PERIODICIDADE_CHOICES": json.dumps(periodicidade_choices, ensure_ascii=False),
        "EXIGENCIA_CHOICES": json.dumps(exigencia_choices, ensure_ascii=False),
        "NIVEL_APLICACAO_CHOICES": json.dumps(nivel_aplicacao_choices, ensure_ascii=False),
        "DOMINIOS_OPTIONS": json.dumps(dominios_options, ensure_ascii=False),
        "preview": {
            "title": "Resumo Rápido",
            "subtitle": "Itens a criar neste lote",
            "items": [],
            "extra_inner_template": "documentos/partials/preview_setup_inteligente.html",
        },
        "form_tips": [
            "Crie primeiro Categorias e Tipos, depois adicione Regras.",
            "Referencie itens novos usando as opções (novo) no select.",
            "Erros deixam a linha em vermelho e impedem o commit.",
        ],
        "model_name": "Setup",
        "form_title": "Setup Inteligente",
    }
    return render(request, "documentos/setup_inteligente.html", context)


# ===================== API BULK =====================
@login_required
@require_POST
def bulk_setup_api(request):
    """API simples (JSON) para criação transacional de categorias, tipos e regras.
    Payload esperado:
    {
        "categorias": [{"temp_id":"cat1","nome":"Fiscal","descricao":""}],
        "tipos": [{"temp_id":"tipo1","nome":"Nota Fiscal","categoria_ref":"cat1","periodicidade":"mensal"}],
        "regras": [{
                "tipo_ref":"tipo1",
                "exigencia":"obrigatorio",
                "nivel_aplicacao":"entidade",
                "escopo":"app",
                "dominio_id": 3,                # Preferencial: referencia FK de DominioDocumento
                "dominio_slug": "fornecedores", # Alternativo ao dominio_id
                "app_label":"fornecedores"     # Legado/fallback se domínio não informado
        }]
    }
    Regras de resolução para escopos 'app' e 'filtro':
        1. Se informado dominio_id, tenta carregar DominioDocumento ativo (ou indiferente) por PK.
        2. Senão, se dominio_slug informado, tenta por slug.
        3. Se domínio resolvido: atribui a FK e também replica seu app_label para campo legado.
        4. Se nenhum domínio resolvido: exige app_label (legado). Caso ausente -> erro.
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    categorias_payload = data.get("categorias") or []
    tipos_payload = data.get("tipos") or []
    regras_payload = data.get("regras") or []

    # Limites simples para evitar abusos
    if len(categorias_payload) > 50 or len(tipos_payload) > 50 or len(regras_payload) > 100:
        return JsonResponse({"error": "Limite excedido."}, status=400)

    resp_map = {"categorias": [], "tipos": [], "regras": []}
    errors = {"categorias": [], "tipos": [], "regras": []}

    # Índices para resolução
    cat_created = {}
    tipo_created = {}

    with transaction.atomic():
        # Categorias
        for item in categorias_payload:
            temp_id = item.get("temp_id")
            nome = (item.get("nome") or "").strip()
            if not nome:
                errors["categorias"].append({"temp_id": temp_id, "errors": {"nome": ["Obrigatório"]}})
                continue
            if CategoriaDocumento.objects.filter(nome__iexact=nome).exists():
                errors["categorias"].append({"temp_id": temp_id, "errors": {"nome": ["Já existe"]}})
                continue
            cat = CategoriaDocumento.objects.create(
                nome=nome,
                descricao=item.get("descricao") or "",
                ativo=item.get("ativo", True),
                ordem=item.get("ordem") or 0,
            )
            cat_created[temp_id] = cat
            resp_map["categorias"].append({"temp_id": temp_id, "id": cat.id})

        # Tipos
        for item in tipos_payload:
            temp_id = item.get("temp_id")
            nome = (item.get("nome") or "").strip()
            cat_ref = item.get("categoria_ref")
            if not nome:
                errors["tipos"].append({"temp_id": temp_id, "errors": {"nome": ["Obrigatório"]}})
                continue
            if not cat_ref:
                errors["tipos"].append({"temp_id": temp_id, "errors": {"categoria_ref": ["Obrigatório"]}})
                continue
            # Resolver categoria (pode ser temp_id ou ID existente)
            categoria_obj = None
            if cat_ref in cat_created:
                categoria_obj = cat_created[cat_ref]
            else:
                try:
                    categoria_obj = CategoriaDocumento.objects.get(pk=int(cat_ref))
                except Exception:
                    errors["tipos"].append(
                        {"temp_id": temp_id, "errors": {"categoria_ref": ["Categoria não encontrada"]}}
                    )
                    continue
            if TipoDocumento.objects.filter(nome__iexact=nome).exists():
                errors["tipos"].append({"temp_id": temp_id, "errors": {"nome": ["Já existe"]}})
                continue
            tipo = TipoDocumento.objects.create(
                nome=nome,
                descricao=item.get("descricao") or "",
                categoria=categoria_obj,
                periodicidade=item.get("periodicidade") or "unico",
                ativo=item.get("ativo", True),
                versionavel=item.get("versionavel", True),
            )
            tipo_created[temp_id] = tipo
            resp_map["tipos"].append({"temp_id": temp_id, "id": tipo.id})

        # Regras
        for idx, item in enumerate(regras_payload):
            tipo_ref = item.get("tipo_ref")
            exigencia = item.get("exigencia") or "obrigatorio"
            escopo = item.get("escopo") or "entidade"
            nivel_aplicacao = item.get("nivel_aplicacao") or "entidade"
            tipo_obj = None
            if not tipo_ref:
                errors["regras"].append({"index": idx, "errors": {"tipo_ref": ["Obrigatório"]}})
                continue
            if tipo_ref in tipo_created:
                tipo_obj = tipo_created[tipo_ref]
            else:
                try:
                    tipo_obj = TipoDocumento.objects.get(pk=int(tipo_ref))
                except Exception:
                    errors["regras"].append({"index": idx, "errors": {"tipo_ref": ["Tipo não encontrado"]}})
                    continue
            regra = RegraDocumento(
                tipo=tipo_obj,
                exigencia=exigencia,
                escopo=escopo,
                nivel_aplicacao=nivel_aplicacao,
                ativo=item.get("ativo", True),
                observacoes=item.get("observacoes") or "",
            )
            # Escopos globais / filtro: preferir domínio
            if escopo in ("app", "filtro"):
                dominio_obj = None
                dominio_id = item.get("dominio_id")
                dominio_slug = item.get("dominio_slug")
                if dominio_id:
                    try:
                        dominio_obj = DominioDocumento.objects.get(pk=int(dominio_id))
                    except Exception:
                        errors["regras"].append({"index": idx, "errors": {"dominio_id": ["Domínio não encontrado"]}})
                        continue
                elif dominio_slug:
                    dominio_obj = DominioDocumento.objects.filter(slug=dominio_slug).first()
                    if not dominio_obj:
                        errors["regras"].append({"index": idx, "errors": {"dominio_slug": ["Domínio não encontrado"]}})
                        continue
                if dominio_obj:
                    regra.dominio = dominio_obj
                    # Replicar app_label legado para compatibilidade
                    regra.app_label = dominio_obj.app_label
                else:
                    # Fallback legado exige app_label explícito
                    legacy_app = item.get("app_label")
                    if not legacy_app:
                        errors["regras"].append(
                            {"index": idx, "errors": {"dominio": ["Informe dominio_id/dominio_slug ou app_label"]}}
                        )
                        continue
                    regra.app_label = legacy_app or "core"
            regra.save()
            resp_map["regras"].append({"index": idx, "id": regra.id, "dominio_id": regra.dominio_id})

        if errors["categorias"] or errors["tipos"] or errors["regras"]:
            # rollback
            transaction.set_rollback(True)
            return JsonResponse({"errors": errors}, status=400)

    return JsonResponse(resp_map, status=201)


@login_required
@require_POST
def regra_transition_ajax(request, regra_id):
    """Transiciona status de uma RegraDocumento.
    POST form/json: acao=aprovar|inativar
    Regras:
      - Apenas superuser (ou futura perm) pode transicionar.
      - aprovar: somente de pendente/rascunho -> aprovada
      - inativar: somente de aprovada -> inativa (também marca ativo=False)
    Retorno sucesso: {success:true,id,status}
    Erro: {success:false, errors:{__all__:[...]}}
    """
    if not request.user.is_superuser and not request.user.has_perm("documentos.change_regradocumento"):
        return JsonResponse({"success": False, "errors": {"__all__": ["Permissão negada"]}}, status=403)
    acao = request.POST.get("acao")
    if request.content_type == "application/json" and not acao:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            acao = payload.get("acao")
        except Exception:
            return JsonResponse({"success": False, "errors": {"__all__": ["JSON inválido"]}}, status=400)
    regra = get_object_or_404(RegraDocumento, pk=regra_id)
    if acao == "aprovar" and regra.status in ("pendente", "rascunho"):
        regra.status = "aprovada"
        regra.save(update_fields=["status"])
    elif acao == "inativar" and regra.status == "aprovada":
        regra.status = "inativa"
        regra.ativo = False
        regra.save(update_fields=["status", "ativo"])
    else:
        return JsonResponse({"success": False, "errors": {"__all__": ["Transição inválida"]}}, status=400)
    return JsonResponse({"success": True, "id": regra.id, "status": regra.get_status_display()})


@login_required
@require_POST
def dominio_create_ajax(request):
    if not request.user.has_perm("documentos.add_dominiodocumento") and not request.user.is_superuser:
        return JsonResponse({"success": False, "errors": {"__all__": ["Permissão negada"]}}, status=403)
    data = request.POST or None
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"success": False, "errors": {"__all__": ["JSON inválido"]}}, status=400)
    form = DominioDocumentoForm(data)
    if form.is_valid():
        dominio = form.save()
        return JsonResponse(
            {
                "success": True,
                "dominio": {
                    "id": dominio.id,
                    "nome": dominio.nome,
                    "slug": dominio.slug,
                    "app_label": dominio.app_label,
                    "ativo": dominio.ativo,
                },
            }
        )
    return JsonResponse({"success": False, "errors": form.errors}, status=400)


# ===================== API WIZARD DOCUMENTOS DINÂMICOS =====================
@login_required
def wizard_docs_list(request):
    try:
        tenant_id = getattr(getattr(request, "tenant", None), "id", None)
        tipos = list(
            TipoDocumento.objects.filter(ativo=True).select_related("categoria").order_by("categoria__ordem", "nome")
        )
        exig = resolver_exigencias_tenant(tenant_id, tipos)
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        temp_qs = (
            WizardTenantDocumentoTemp.objects.filter(tenant_id=tenant_id)
            if tenant_id
            else WizardTenantDocumentoTemp.objects.filter(session_key=session_key)
        )
        temp_map = {t.tipo_id: t for t in temp_qs}
        obrigatorios, opcionais = [], []
        for tp in tipos:
            try:
                categoria_nome = tp.categoria.nome if tp.categoria_id else "-"  # segurança
            except Exception:  # categoria eventualmente deletada
                categoria_nome = "-"
            item = {
                "tipo_id": tp.id,
                "nome": tp.nome,
                "categoria": categoria_nome,
                "periodicidade": tp.get_periodicidade_display(),
                "exigencia": exig.get(tp.id, "opcional"),
                "uploaded": tp.id in temp_map,
            }
            if item["uploaded"]:
                tmp = temp_map[tp.id]
                item["temp_id"] = tmp.id
                item["filename"] = tmp.filename_original
                item["tamanho"] = tmp.tamanho_bytes
            (obrigatorios if item["exigencia"] == "obrigatorio" else opcionais).append(item)
        return JsonResponse({"obrigatorios": obrigatorios, "opcionais": opcionais})
    except Exception as e:
        # Log simples (evitar crash). Em produção substituir por logger.
        import traceback

        tb = traceback.format_exc(limit=3)
        return JsonResponse({"error": "falha_interna", "detail": str(e), "trace": tb}, status=500)


@login_required
@require_POST
def wizard_docs_upload(request):
    tipo_id = request.POST.get("tipo_id")
    arquivo = request.FILES.get("arquivo")
    if not (tipo_id and arquivo):
        return JsonResponse({"ok": False, "error": "Dados incompletos"}, status=400)
    try:
        tipo = TipoDocumento.objects.get(pk=int(tipo_id), ativo=True)
    except Exception:
        return JsonResponse({"ok": False, "error": "Tipo inválido"}, status=404)
    tenant_id = getattr(getattr(request, "tenant", None), "id", None)
    session_key = request.session.session_key or request.session.save() or request.session.session_key
    exig = resolver_exigencias_tenant(tenant_id, [tipo]).get(tipo.id, "opcional")
    # Substituir upload anterior se existir
    existing = (
        WizardTenantDocumentoTemp.objects.filter(tipo=tipo, tenant_id=tenant_id)
        if tenant_id
        else WizardTenantDocumentoTemp.objects.filter(tipo=tipo, session_key=session_key)
    )
    existing.delete()
    temp = WizardTenantDocumentoTemp.objects.create(
        tenant_id=tenant_id,
        session_key=None if tenant_id else session_key,
        tipo=tipo,
        obrigatorio_snapshot=(exig == "obrigatorio"),
        nome_tipo_cache=tipo.nome,
        arquivo=arquivo,
        filename_original=arquivo.name,
        tamanho_bytes=arquivo.size,
    )
    return JsonResponse(
        {
            "ok": True,
            "temp_id": temp.id,
            "tipo_id": tipo.id,
            "filename": temp.filename_original,
            "tamanho": temp.tamanho_bytes,
        }
    )


@login_required
@require_POST
def wizard_docs_delete(request, temp_id):
    tenant_id = getattr(getattr(request, "tenant", None), "id", None)
    session_key = request.session.session_key
    try:
        obj = WizardTenantDocumentoTemp.objects.get(pk=temp_id)
    except WizardTenantDocumentoTemp.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Não encontrado"}, status=404)
    if (tenant_id and obj.tenant_id == tenant_id) or (not tenant_id and obj.session_key == session_key):
        obj.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": "Permissão negada"}, status=403)

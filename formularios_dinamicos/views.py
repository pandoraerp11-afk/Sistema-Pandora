import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from core.utils import get_current_tenant

from .forms import (
    CampoFormularioForm,
    FiltroFormularioForm,
    FiltroRespostaForm,
    FormularioDinamicoForm,
    RespostaFormularioForm,
)
from .models import (
    ArquivoResposta,
    CampoFormulario,
    FormularioDinamico,
    LogFormulario,
    RespostaFormulario,
    StatusResposta,
    TemplateFormulario,
)


@login_required
@login_required
def formularios_dinamicos_home(request):
    """
    View para o dashboard de Formulários Dinâmicos, mostrando estatísticas e dados relevantes.
    """
    template_name = "formularios_dinamicos/formularios_dinamicos_home.html"
    tenant = get_current_tenant(request)

    if not tenant:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Formulários Dinâmicos"),
        "subtitulo": _("Visão geral do módulo Formulários Dinâmicos"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


def form_list(request):
    """Lista de formulários dinâmicos"""

    form = FiltroFormularioForm(request.GET)
    formularios = FormularioDinamico.objects.all()

    # Aplicar filtros
    if form.is_valid():
        busca = form.cleaned_data.get("busca")
        if busca:
            formularios = formularios.filter(
                Q(titulo__icontains=busca) | Q(descricao__icontains=busca) | Q(slug__icontains=busca)
            )

        status = form.cleaned_data.get("status")
        if status:
            formularios = formularios.filter(status=status)

        publico = form.cleaned_data.get("publico")
        if publico == "true":
            formularios = formularios.filter(publico=True)
        elif publico == "false":
            formularios = formularios.filter(publico=False)

        criado_por = form.cleaned_data.get("criado_por")
        if criado_por:
            formularios = formularios.filter(criado_por=criado_por)

    # Adicionar estatísticas
    formularios = formularios.annotate(total_respostas=Count("respostas")).order_by("-criado_em")

    # Paginação
    paginator = Paginator(formularios, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "form": form,
        "page_obj": page_obj,
        "formularios": page_obj,
    }

    return render(request, "formularios_dinamicos/form_list_ultra_modern.html", context)


@login_required
def form_create(request):
    """Criar novo formulário dinâmico"""

    if request.method == "POST":
        form = FormularioDinamicoForm(request.POST)
        if form.is_valid():
            formulario = form.save(commit=False)
            formulario.criado_por = request.user
            formulario.save()

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user,
                acao="CREATE",
                descricao=f'Formulário "{formulario.titulo}" criado',
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, f'Formulário "{formulario.titulo}" criado com sucesso!')
            return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)
    else:
        form = FormularioDinamicoForm()

    context = {
        "form": form,
        "title": "Criar Novo Formulário",
    }

    return render(request, "formularios_dinamicos/form_form_ultra_modern.html", context)


@login_required
def form_detail(request, pk):
    """Detalhes do formulário dinâmico"""

    formulario = get_object_or_404(FormularioDinamico, pk=pk)

    # Estatísticas
    total_respostas = formulario.respostas.count()
    respostas_por_status = formulario.respostas.values("status").annotate(total=Count("id")).order_by("status")

    # Campos do formulário
    campos = formulario.campos.all().order_by("ordem")

    # Respostas recentes
    respostas_recentes = formulario.respostas.select_related("usuario").order_by("-criado_em")[:10]

    context = {
        "formulario": formulario,
        "total_respostas": total_respostas,
        "respostas_por_status": respostas_por_status,
        "campos": campos,
        "respostas_recentes": respostas_recentes,
    }

    return render(request, "formularios_dinamicos/form_detail_ultra_modern.html", context)


@login_required
def form_update(request, pk):
    """Atualizar formulário dinâmico"""

    formulario = get_object_or_404(FormularioDinamico, pk=pk)

    if request.method == "POST":
        form = FormularioDinamicoForm(request.POST, instance=formulario)
        if form.is_valid():
            form.save()

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user,
                acao="UPDATE",
                descricao=f'Formulário "{formulario.titulo}" atualizado',
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, f'Formulário "{formulario.titulo}" atualizado com sucesso!')
            return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)
    else:
        form = FormularioDinamicoForm(instance=formulario)

    context = {
        "form": form,
        "formulario": formulario,
        "title": f"Editar Formulário: {formulario.titulo}",
    }

    return render(request, "formularios_dinamicos/form_form_ultra_modern.html", context)


@login_required
def campo_create(request, form_pk):
    """Criar novo campo para o formulário"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)

    if request.method == "POST":
        form = CampoFormularioForm(request.POST)
        if form.is_valid():
            campo = form.save(commit=False)
            campo.formulario = formulario
            campo.save()

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user,
                acao="ADD_FIELD",
                descricao=f'Campo "{campo.label}" adicionado ao formulário',
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, f'Campo "{campo.label}" adicionado com sucesso!')
            return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)
    else:
        # Definir ordem padrão
        ultima_ordem = formulario.campos.aggregate(max_ordem=Max("ordem"))["max_ordem"] or 0

        form = CampoFormularioForm(initial={"ordem": ultima_ordem + 1})

    context = {
        "form": form,
        "formulario": formulario,
        "title": f"Adicionar Campo - {formulario.titulo}",
    }

    return render(request, "formularios_dinamicos/campo_form_ultra_modern.html", context)


@login_required
def campo_update(request, form_pk, campo_pk):
    """Atualizar campo do formulário"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)
    campo = get_object_or_404(CampoFormulario, pk=campo_pk, formulario=formulario)

    if request.method == "POST":
        form = CampoFormularioForm(request.POST, instance=campo)
        if form.is_valid():
            form.save()

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user,
                acao="UPDATE_FIELD",
                descricao=f'Campo "{campo.label}" atualizado',
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, f'Campo "{campo.label}" atualizado com sucesso!')
            return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)
    else:
        form = CampoFormularioForm(instance=campo)

    context = {
        "form": form,
        "formulario": formulario,
        "campo": campo,
        "title": f"Editar Campo: {campo.label}",
    }

    return render(request, "formularios_dinamicos/campo_form_ultra_modern.html", context)


@login_required
def campo_delete(request, form_pk, campo_pk):
    """Excluir campo do formulário"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)
    campo = get_object_or_404(CampoFormulario, pk=campo_pk, formulario=formulario)

    if request.method == "POST":
        nome_campo = campo.label
        campo.delete()

        # Log da atividade
        LogFormulario.objects.create(
            formulario=formulario,
            usuario=request.user,
            acao="DELETE_FIELD",
            descricao=f'Campo "{nome_campo}" removido do formulário',
            ip_address=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        messages.success(request, f'Campo "{nome_campo}" removido com sucesso!')

    return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)


def form_render(request, slug):
    """Renderizar formulário para preenchimento"""

    formulario = get_object_or_404(FormularioDinamico, slug=slug)

    # Verificar se o formulário está ativo
    if not formulario.esta_ativo:
        messages.error(request, "Este formulário não está disponível no momento.")
        return redirect("dashboard")

    # Verificar se requer login
    if formulario.requer_login and not request.user.is_authenticated:
        messages.error(request, "Você precisa estar logado para acessar este formulário.")
        return redirect("core:login")

    # Verificar se permite múltiplas respostas
    if not formulario.permite_multiplas_respostas and request.user.is_authenticated:
        resposta_existente = formulario.respostas.filter(usuario=request.user).first()
        if resposta_existente:
            messages.info(request, "Você já respondeu este formulário.")
            return redirect("formularios_dinamicos:resposta_detail", form_slug=slug, token=resposta_existente.token)

    if request.method == "POST":
        form = RespostaFormularioForm(formulario, request.POST, request.FILES)
        if form.is_valid():
            # Criar resposta
            resposta = RespostaFormulario.objects.create(
                formulario=formulario,
                usuario=request.user if request.user.is_authenticated else None,
                dados=form.cleaned_data,
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                status=StatusResposta.ENVIADO,
                enviado_em=timezone.now(),
            )

            # Processar arquivos
            for campo in formulario.campos.filter(tipo__in=["file", "image"]):
                arquivo = request.FILES.get(campo.nome)
                if arquivo:
                    ArquivoResposta.objects.create(
                        resposta=resposta,
                        campo=campo.nome,
                        arquivo=arquivo,
                        nome_original=arquivo.name,
                        tamanho=arquivo.size,
                        tipo_mime=arquivo.content_type,
                    )

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user if request.user.is_authenticated else None,
                acao="SUBMIT_RESPONSE",
                descricao="Nova resposta enviada para o formulário",
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, "Formulário enviado com sucesso!")
            return redirect("formularios_dinamicos:resposta_detail", form_slug=slug, token=resposta.token)
    else:
        form = RespostaFormularioForm(formulario)

    context = {
        "formulario": formulario,
        "form": form,
    }

    return render(request, "formularios_dinamicos/form_render_ultra_modern.html", context)


@login_required
def resposta_list(request, form_pk):
    """Lista de respostas do formulário"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)

    form = FiltroRespostaForm(request.GET)
    respostas = formulario.respostas.select_related("usuario", "analisado_por")

    # Aplicar filtros
    if form.is_valid():
        status = form.cleaned_data.get("status")
        if status:
            respostas = respostas.filter(status=status)

        usuario = form.cleaned_data.get("usuario")
        if usuario:
            respostas = respostas.filter(usuario=usuario)

        data_inicio = form.cleaned_data.get("data_inicio")
        if data_inicio:
            respostas = respostas.filter(criado_em__date__gte=data_inicio)

        data_fim = form.cleaned_data.get("data_fim")
        if data_fim:
            respostas = respostas.filter(criado_em__date__lte=data_fim)

    respostas = respostas.order_by("-criado_em")

    # Paginação
    paginator = Paginator(respostas, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "formulario": formulario,
        "form": form,
        "page_obj": page_obj,
        "respostas": page_obj,
    }

    return render(request, "formularios_dinamicos/resposta_list_ultra_modern.html", context)


def resposta_detail(request, form_slug, token):
    """Detalhes da resposta"""

    formulario = get_object_or_404(FormularioDinamico, slug=form_slug)
    resposta = get_object_or_404(RespostaFormulario, formulario=formulario, token=token)

    # Verificar permissão
    if request.user.is_authenticated:
        # Usuário logado pode ver suas próprias respostas ou se for admin
        if resposta.usuario != request.user and not request.user.is_staff:
            messages.error(request, "Você não tem permissão para ver esta resposta.")
            return redirect("dashboard")
    # Usuário anônimo só pode ver se o formulário for público
    elif not formulario.publico:
        messages.error(request, "Você não tem permissão para ver esta resposta.")
        return redirect("core:login")

    # Organizar dados da resposta
    dados_organizados = []
    for campo in formulario.campos.all().order_by("ordem"):
        valor = resposta.get_valor_campo(campo.nome)
        dados_organizados.append(
            {
                "campo": campo,
                "valor": valor,
            }
        )

    context = {
        "formulario": formulario,
        "resposta": resposta,
        "dados_organizados": dados_organizados,
    }

    return render(request, "formularios_dinamicos/resposta_detail_ultra_modern.html", context)


@login_required
def resposta_update_status(request, form_pk, resposta_pk):
    """Atualizar status da resposta"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)
    resposta = get_object_or_404(RespostaFormulario, pk=resposta_pk, formulario=formulario)

    if request.method == "POST":
        novo_status = request.POST.get("status")
        observacoes = request.POST.get("observacoes", "")

        if novo_status in [choice[0] for choice in StatusResposta.choices]:
            status_anterior = resposta.status
            resposta.status = novo_status
            resposta.analisado_por = request.user
            resposta.analisado_em = timezone.now()
            resposta.observacoes_analise = observacoes
            resposta.save()

            # Log da atividade
            LogFormulario.objects.create(
                formulario=formulario,
                usuario=request.user,
                acao="UPDATE_RESPONSE_STATUS",
                descricao=f'Status da resposta alterado de "{status_anterior}" para "{novo_status}"',
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

            messages.success(request, "Status da resposta atualizado com sucesso!")

    return redirect("formularios_dinamicos:resposta_list", form_pk=formulario.pk)


# API Views
@login_required
def api_form_stats(request, pk):
    """API para estatísticas do formulário"""

    formulario = get_object_or_404(FormularioDinamico, pk=pk)

    stats = {
        "total_respostas": formulario.respostas.count(),
        "respostas_por_status": list(
            formulario.respostas.values("status").annotate(total=Count("id")).order_by("status")
        ),
        "respostas_por_dia": list(
            formulario.respostas.extra(select={"dia": "date(criado_em)"})
            .values("dia")
            .annotate(total=Count("id"))
            .order_by("dia")[-30:]  # Últimos 30 dias
        ),
    }

    return JsonResponse(stats)


@login_required
@require_http_methods(["POST"])
def api_campo_reorder(request, form_pk):
    """API para reordenar campos"""

    formulario = get_object_or_404(FormularioDinamico, pk=form_pk)

    try:
        data = json.loads(request.body)
        campo_ids = data.get("campo_ids", [])

        for index, campo_id in enumerate(campo_ids):
            CampoFormulario.objects.filter(id=campo_id, formulario=formulario).update(ordem=index)

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def template_list(request):
    """Lista de templates de formulários"""

    templates = TemplateFormulario.objects.filter(ativo=True).order_by("categoria", "nome")

    context = {
        "templates": templates,
    }

    return render(request, "formularios_dinamicos/template_list_ultra_modern.html", context)


@login_required
def form_from_template(request, template_pk):
    """Criar formulário a partir de template"""

    template = get_object_or_404(TemplateFormulario, pk=template_pk, ativo=True)

    try:
        # Criar formulário baseado no template
        configuracao = template.configuracao

        formulario = FormularioDinamico.objects.create(
            titulo=f"{template.nome} - {timezone.now().strftime('%d/%m/%Y')}",
            descricao=configuracao.get("descricao", ""),
            slug=f"{template.nome.lower().replace(' ', '-')}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            criado_por=request.user,
            **configuracao.get("formulario", {}),
        )

        # Criar campos
        for campo_config in configuracao.get("campos", []):
            CampoFormulario.objects.create(formulario=formulario, **campo_config)

        messages.success(request, f'Formulário criado a partir do template "{template.nome}"!')
        return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)

    except Exception as e:
        messages.error(request, f"Erro ao criar formulário: {str(e)}")
        return redirect("formularios_dinamicos:template_list")


@login_required
def template_list(request):
    """Lista de modelos de formulário"""
    templates = TemplateFormulario.objects.all()
    context = {
        "templates": templates,
    }
    return render(request, "formularios_dinamicos/template_list_ultra_modern.html", context)


@login_required
def form_from_template(request, template_pk):
    """Cria um novo formulário a partir de um modelo"""
    template = get_object_or_404(TemplateFormulario, pk=template_pk)

    if request.method == "POST":
        form = FormularioDinamicoForm(request.POST)
        if form.is_valid():
            formulario = form.save(commit=False)
            formulario.criado_por = request.user
            formulario.save()

            # Copiar campos do modelo para o novo formulário
            for campo_modelo in template.campos.all():
                CampoFormulario.objects.create(
                    formulario=formulario,
                    label=campo_modelo.label,
                    nome=campo_modelo.nome,
                    tipo=campo_modelo.tipo,
                    obrigatorio=campo_modelo.obrigatorio,
                    opcoes=campo_modelo.opcoes,
                    ordem=campo_modelo.ordem,
                )

            messages.success(
                request, f'Formulário "{formulario.titulo}" criado a partir do modelo "{template.titulo}" com sucesso!'
            )
            return redirect("formularios_dinamicos:form_detail", pk=formulario.pk)
    else:
        # Preencher o formulário com dados do modelo, se aplicável
        initial_data = {
            "titulo": f"Cópia de {template.titulo}",
            "descricao": template.descricao,
            "status": template.status,
            "publico": template.publico,
            "requer_login": template.requer_login,
            "permite_multiplas_respostas": template.permite_multiplas_respostas,
        }
        form = FormularioDinamicoForm(initial=initial_data)

    context = {
        "form": form,
        "template": template,
        "title": f"Criar Formulário a partir do Modelo: {template.titulo}",
    }

    return render(request, "formularios_dinamicos/form_form_ultra_modern.html", context)

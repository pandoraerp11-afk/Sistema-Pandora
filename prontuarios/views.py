from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from core.mixins import ModuleRequiredMixin, TenantRequiredMixin
from core.utils import get_current_tenant

from .forms import AnamneseForm, AtendimentoForm, FotoEvolucaoForm, PerfilClinicoForm
from .models import Anamnese, Atendimento, FotoEvolucao, PerfilClinico


@login_required
def prontuarios_home(request):
    """
    View para o dashboard de Prontuários, mostrando estatísticas e dados relevantes.
    """
    template_name = "prontuarios/prontuarios_home.html"
    tenant = get_current_tenant(request)

    # Superusuário não precisa selecionar empresa
    if not tenant and not request.user.is_superuser:
        messages.error(request, _("Por favor, selecione uma empresa para ver o dashboard."))
        return redirect(reverse("core:tenant_select"))

    context = {
        "titulo": _("Prontuários"),
        "subtitulo": _("Visão geral do módulo Prontuários"),
        "tenant": tenant,
    }

    return render(request, template_name, context)


"""Views de Paciente removidas – modelo consolidado em Cliente."""


# Views para Serviço (as telas específicas foram movidas para o app 'servicos')
class TenantSafeMixin:
    """Fornece método robusto para obter tenant atual evitando AttributeError caso usuário não tenha atributo tenant ou não selecionou empresa."""

    def get_tenant(self):
        tenant = get_current_tenant(self.request)
        if tenant:
            return tenant
        return getattr(self.request.user, "tenant", None)


# === VIEWS DE PROCEDIMENTO REMOVIDAS ===
# As views de Procedimento (legado) foram migradas para o app 'servicos'.
# Utilize as views de Servico no lugar.


# Views para Atendimento
class AtendimentoListView(LoginRequiredMixin, TenantSafeMixin, ListView):
    model = Atendimento
    template_name = "prontuarios/atendimento_list.html"
    context_object_name = "atendimentos"

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return Atendimento.objects.none()
        qs = Atendimento.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(profissional=user)


class AtendimentoDetailView(LoginRequiredMixin, TenantSafeMixin, DetailView):
    model = Atendimento
    template_name = "prontuarios/atendimento_detail.html"
    context_object_name = "atendimento"

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return Atendimento.objects.none()
        qs = Atendimento.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(profissional=user)


class AtendimentoCreateView(LoginRequiredMixin, TenantSafeMixin, CreateView):
    model = Atendimento
    form_class = AtendimentoForm
    template_name = "prontuarios/atendimento_form.html"
    success_url = reverse_lazy("prontuarios:atendimentos_list")

    def form_valid(self, form):
        # Centralização: Prontuários não manipula capacidade de slots no create.
        tenant = self.get_tenant()
        form.instance.tenant = tenant
        if not self.request.user.is_superuser:
            form.instance.profissional = self.request.user
        resp = super().form_valid(form)
        messages.success(self.request, _("Atendimento criado com sucesso."))
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.urls import reverse

        ctx["cancel_url"] = reverse("prontuarios:atendimentos_list")
        return ctx


class AtendimentoUpdateView(LoginRequiredMixin, TenantSafeMixin, UpdateView):
    model = Atendimento
    form_class = AtendimentoForm
    template_name = "prontuarios/atendimento_form.html"
    success_url = reverse_lazy("prontuarios:atendimentos_list")

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return Atendimento.objects.none()
        qs = Atendimento.objects.filter(tenant=tenant)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(profissional=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.urls import reverse

        ctx["cancel_url"] = reverse("prontuarios:atendimentos_list")
        return ctx

    def form_valid(self, form):
        # Centralização: Prontuários não manipula capacidade de slots.
        # Apenas atualiza o Atendimento e exibe mensagem.
        resp = super().form_valid(form)
        messages.success(self.request, _("Atendimento atualizado com sucesso."))
        return resp

    # Removido fallback de liberação de slot: gestão de slots é do módulo Agendamentos.


class AtendimentoDeleteView(LoginRequiredMixin, TenantSafeMixin, DeleteView):
    model = Atendimento
    template_name = "prontuarios/atendimento_confirm_delete.html"
    success_url = reverse_lazy("prontuarios:atendimentos_list")

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return Atendimento.objects.none()
        return Atendimento.objects.filter(tenant=tenant)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Atendimento excluído."))
        return super().delete(request, *args, **kwargs)


# Views para FotoEvolucao
class FotoEvolucaoListView(LoginRequiredMixin, TenantSafeMixin, ListView):
    model = FotoEvolucao
    template_name = "prontuarios/fotoevolucao_list.html"
    context_object_name = "fotos_evolucao"
    paginate_by = 20

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return FotoEvolucao.objects.none()
        qs = FotoEvolucao.objects.filter(tenant=tenant)
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(atendimento__profissional=user)
        p = self.request.GET
        if p.get("servico"):
            qs = qs.filter(atendimento__servico_id=p.get("servico"))
        if p.get("tipo_foto"):
            qs = qs.filter(tipo_foto=p.get("tipo_foto"))
        if p.get("momento"):
            qs = qs.filter(momento=p.get("momento"))
        if p.get("data_ini"):
            qs = qs.filter(data_foto__date__gte=p.get("data_ini"))
        if p.get("data_fim"):
            qs = qs.filter(data_foto__date__lte=p.get("data_fim"))
        if p.get("q"):
            from django.db.models import Q

            qtxt = p.get("q")
            qs = qs.filter(
                Q(titulo__icontains=qtxt) | Q(area_fotografada__icontains=qtxt) | Q(observacoes__icontains=qtxt)
            )
        order = p.get("order", "-data_foto")
        if order not in ["data_foto", "-data_foto", "titulo", "-titulo"]:
            order = "-data_foto"
        return qs.select_related("atendimento", "atendimento__servico").order_by(order)

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Retorna somente bloco de tabela para lazy load
            return super().render_to_response(context, **response_kwargs)
        return super().render_to_response(context, **response_kwargs)


class FotoEvolucaoDetailView(LoginRequiredMixin, TenantSafeMixin, DetailView):
    model = FotoEvolucao
    template_name = "prontuarios/fotoevolucao_detail.html"
    context_object_name = "foto_evolucao"

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return FotoEvolucao.objects.none()
        qs = FotoEvolucao.objects.filter(tenant=tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(atendimento__profissional=user)


class FotoEvolucaoCreateView(LoginRequiredMixin, TenantSafeMixin, CreateView):
    model = FotoEvolucao
    form_class = FotoEvolucaoForm
    template_name = "prontuarios/fotoevolucao_form.html"
    success_url = reverse_lazy("prontuarios:fotos_evolucao_list")

    def form_valid(self, form):
        tenant = self.get_tenant()
        if not tenant:
            messages.error(self.request, _("Selecione uma empresa antes de criar fotos."))
            return redirect("core:tenant_select")
        form.instance.tenant = tenant
        return super().form_valid(form)


class FotoEvolucaoUpdateView(LoginRequiredMixin, TenantSafeMixin, UpdateView):
    model = FotoEvolucao
    form_class = FotoEvolucaoForm
    template_name = "prontuarios/fotoevolucao_form.html"
    success_url = reverse_lazy("prontuarios:fotos_evolucao_list")

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return FotoEvolucao.objects.none()
        qs = FotoEvolucao.objects.filter(tenant=tenant)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(atendimento__profissional=self.request.user)


class FotoEvolucaoDeleteView(LoginRequiredMixin, TenantSafeMixin, DeleteView):
    model = FotoEvolucao
    template_name = "prontuarios/fotoevolucao_confirm_delete.html"
    success_url = reverse_lazy("prontuarios:fotos_evolucao_list")

    def get_queryset(self):
        tenant = self.get_tenant()
        if not tenant:
            return FotoEvolucao.objects.none()
        qs = FotoEvolucao.objects.filter(tenant=tenant)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(atendimento__profissional=self.request.user)


# Views para Anamnese
class AnamneseListView(LoginRequiredMixin, ListView):
    model = Anamnese
    template_name = "prontuarios/anamnese_list.html"
    context_object_name = "anamneses"

    def get_queryset(self):
        qs = Anamnese.objects.filter(tenant=self.request.user.tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(profissional_responsavel=user)


class AnamneseDetailView(LoginRequiredMixin, DetailView):
    model = Anamnese
    template_name = "prontuarios/anamnese_detail.html"
    context_object_name = "anamnese"

    def get_queryset(self):
        qs = Anamnese.objects.filter(tenant=self.request.user.tenant)
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(profissional_responsavel=user)


class AnamneseCreateView(LoginRequiredMixin, CreateView):
    model = Anamnese
    form_class = AnamneseForm
    template_name = "prontuarios/anamnese_form.html"
    success_url = reverse_lazy("prontuarios:anamneses_list")

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        if not self.request.user.is_superuser:
            form.instance.profissional_responsavel = self.request.user
        return super().form_valid(form)


class AnamneseUpdateView(LoginRequiredMixin, UpdateView):
    model = Anamnese
    form_class = AnamneseForm
    template_name = "prontuarios/anamnese_form.html"
    success_url = reverse_lazy("prontuarios:anamneses_list")

    def get_queryset(self):
        qs = Anamnese.objects.filter(tenant=self.request.user.tenant)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(profissional_responsavel=self.request.user)


class AnamneseDeleteView(LoginRequiredMixin, DeleteView):
    model = Anamnese
    template_name = "prontuarios/anamnese_confirm_delete.html"
    success_url = reverse_lazy("prontuarios:anamneses_list")

    def get_queryset(self):
        qs = Anamnese.objects.filter(tenant=self.request.user.tenant)
        if self.request.user.is_superuser:
            return qs
        return qs.filter(profissional_responsavel=self.request.user)


# Views para Perfil Clínico
class PerfilClinicoListView(LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, ListView):
    required_module = "prontuarios"
    model = PerfilClinico
    template_name = "prontuarios/perfilclinico_list.html"
    context_object_name = "perfis"

    def get_queryset(self):
        return PerfilClinico.objects.filter(tenant=self.request.user.tenant)


class PerfilClinicoDetailView(LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, DetailView):
    required_module = "prontuarios"
    model = PerfilClinico
    template_name = "prontuarios/perfilclinico_detail.html"
    context_object_name = "perfil"

    def get_queryset(self):
        return PerfilClinico.objects.filter(tenant=self.request.user.tenant)


class PerfilClinicoCreateView(LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, CreateView):
    required_module = "prontuarios"
    model = PerfilClinico
    form_class = PerfilClinicoForm
    template_name = "prontuarios/perfilclinico_form.html"
    success_url = reverse_lazy("prontuarios:perfils_clinicos_list")

    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        return super().form_valid(form)


class PerfilClinicoUpdateView(LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, UpdateView):
    required_module = "prontuarios"
    model = PerfilClinico
    form_class = PerfilClinicoForm
    template_name = "prontuarios/perfilclinico_form.html"
    success_url = reverse_lazy("prontuarios:perfils_clinicos_list")

    def get_queryset(self):
        return PerfilClinico.objects.filter(tenant=self.request.user.tenant)


class PerfilClinicoDeleteView(LoginRequiredMixin, TenantRequiredMixin, ModuleRequiredMixin, DeleteView):
    required_module = "prontuarios"
    model = PerfilClinico
    template_name = "prontuarios/perfilclinico_confirm_delete.html"
    success_url = reverse_lazy("prontuarios:perfils_clinicos_list")

    def get_queryset(self):
        return PerfilClinico.objects.filter(tenant=self.request.user.tenant)


# === Disponibilidades & Slots (UI simples) ===
"""Views de Disponibilidade e Slot removidas: gestão está no módulo Agendamentos."""


class ProntuariosIndexView(LoginRequiredMixin, TemplateView):
    template_name = "prontuarios/prontuarios_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

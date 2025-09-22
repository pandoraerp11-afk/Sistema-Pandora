# clientes/wizard_views.py - Wizard de Clientes alinhado ao padrão do CORE/Fornecedores
"""Wizard de Clientes reutilizando os templates do CORE para os Steps 1–3 (Identificação,
Endereços, Contatos), com chaves de sessão isoladas e rotas de navegação direta (goto).
Mantém documentos e confirmação específicos deste módulo.
"""

import contextlib
import logging
from typing import Any

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from core.models import TenantUser
from core.wizard_extensions import ClienteWizardMixin
from core.wizard_forms import (
    TenantAddressWizardForm,
    TenantContactsWizardForm,
)

# Importar o wizard EXISTENTE do core (sem modificar)
from core.wizard_views import TenantCreationWizardView

# Modelos específicos de clientes
from .models import Cliente, EnderecoAdicional, PessoaFisica, PessoaJuridica

# Formulários específicos do wizard de clientes
from .wizard_forms import (
    ClienteDocumentsWizardForm,
    ClientePFIdentificationForm,
    ClientePJIdentificationForm,
    ClienteReviewWizardForm,
)

logger = logging.getLogger(__name__)

# Mapeamento de steps para clientes (reutilizando templates do CORE nos passos 1–3)
CLIENTE_WIZARD_STEPS = {
    1: {
        "name": "Identificação",
        "form_classes": {
            # Reutiliza os formulários completos do CORE (adaptados) com o mesmo UX
            "pj": ClientePJIdentificationForm,
            "pf": ClientePFIdentificationForm,
        },
        # Template compartilhado do CORE
        "template": "core/wizard/step_identification.html",
        "icon": "fas fa-user",
        "description": "Dados básicos do cliente",
    },
    2: {
        "name": "Endereços",
        "form_classes": {"main": TenantAddressWizardForm},
        "template": "core/wizard/step_address.html",
        "icon": "fas fa-map-marker-alt",
        "description": "Endereço principal",
    },
    3: {
        "name": "Contatos",
        "form_classes": {"main": TenantContactsWizardForm},
        "template": "core/wizard/step_contacts.html",
        "icon": "fas fa-phone",
        "description": "Contatos adicionais",
    },
    4: {
        "name": "Documentos",
        "form_classes": {"main": ClienteDocumentsWizardForm},
        # Mantém o template deste módulo ou troque para 'core/wizard/step_documents.html' se desejar unificar
        "template": "clientes/wizard/step_documents.html",
        "icon": "fas fa-file-alt",
        "description": "Documentos (opcional)",
    },
    5: {
        "name": "Confirmação",
        "form_classes": {"main": ClienteReviewWizardForm},
        "template": "clientes/wizard/step_confirmation.html",
        "icon": "fas fa-check-circle",
        "description": "Revisão e confirmação",
    },
}


class ClienteWizardView(ClienteWizardMixin, TenantCreationWizardView):
    """Wizard para clientes BASEADO no wizard de tenants
    Herda TODA a funcionalidade existente e apenas customiza o mínimo necessário
    """

    # Configurações específicas de clientes
    success_url = reverse_lazy("clientes:clientes_list")

    # OVERRIDE FUNDAMENTAL: Definir os wizard steps específicos como propriedade da classe
    @property
    def wizard_steps(self):
        """Retorna os steps específicos para clientes"""
        return CLIENTE_WIZARD_STEPS

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch para lidar com super admins corretamente"""
        if request.user.is_superuser:
            # Super admins têm acesso direto, mas precisam anexar tenant se disponível
            request.tenant = self.get_current_tenant(request)
            return super(TenantCreationWizardView, self).dispatch(request, *args, **kwargs)
        # Usuários normais precisam de tenant obrigatório
        request.tenant = self.get_current_tenant(request)
        if not request.tenant:
            messages.error(request, _("Nenhuma empresa selecionada. Por favor, escolha uma para continuar."))
            return redirect("core:tenant_select")

        # Verifica se o usuário tem acesso ao tenant
        has_access = TenantUser.objects.filter(tenant=request.tenant, user=request.user).exists()
        if not has_access:
            messages.error(request, _("Você não tem permissão para acessar esta empresa."))
            return redirect("core:tenant_select")

        return super(TenantCreationWizardView, self).dispatch(request, *args, **kwargs)

    def get_current_tenant(self, request):
        """Método auxiliar para pegar o tenant atual"""
        try:
            from core.utils import get_current_tenant

            return get_current_tenant(request)
        except Exception:
            return None

    def test_func(self) -> bool:
        """Para clientes: super admins sempre têm acesso, outros precisam de tenant"""
        if self.request.user.is_superuser:
            return True
        return hasattr(self.request, "tenant") and self.request.tenant is not None

    def get_wizard_steps(self) -> dict[int, dict[str, Any]]:
        """Retorna os steps específicos para clientes"""
        return CLIENTE_WIZARD_STEPS

    def get_current_step(self) -> int:
        """Isola as chaves de sessão para o wizard de clientes."""
        return self.request.session.get("client_wizard_step", 1)

    def set_current_step(self, step: int) -> None:
        """Isola as chaves de sessão para o wizard de clientes."""
        self.request.session["client_wizard_step"] = step
        self.request.session.modified = True

    def get_wizard_data(self) -> dict[str, Any]:
        """Isola os dados do wizard de clientes."""
        return self.request.session.get("client_wizard_data", {})

    def set_wizard_data(self, step: int, data: dict[str, Any]) -> None:
        """Isola os dados do wizard de clientes."""
        wizard_data = self.get_wizard_data()
        wizard_data[f"step_{step}"] = data
        self.request.session["client_wizard_data"] = wizard_data
        self.request.session.modified = True

    def clear_wizard_data(self) -> None:
        """Limpa os dados do wizard de clientes."""
        self.request.session.pop("client_wizard_step", None)
        self.request.session.pop("client_wizard_data", None)
        # Limpa eventuais arquivos temporários compatíveis com o core, se existirem
        with contextlib.suppress(Exception):
            self.clear_temp_files()
        self.request.session.modified = True

    def process_step_data(self, forms):
        """Processa dados dos formulários (reutiliza lógica do pai)"""
        step_data = {}
        for form_key, form in forms.items():
            if form.is_valid():
                cleaned_data = form.cleaned_data.copy()
                step_data[form_key] = cleaned_data
        return step_data

    def finish_wizard(self):
        """Finaliza o wizard criando ou atualizando o cliente (PF/PJ) e demais steps."""
        editing_entity = self.kwargs.get("pk")
        try:
            with transaction.atomic():
                wizard_data = self.get_wizard_data() or {}
                step_1_data = wizard_data.get("step_1", {}) or {}
                if not step_1_data:
                    messages.error(self.request, "Dados de identificação não encontrados.")
                    return redirect("clientes:clientes_list")

                tenant = getattr(self.request, "tenant", None)
                if not tenant:
                    messages.error(self.request, "Nenhuma empresa selecionada.")
                    return redirect("clientes:clientes_list")

                tipo = self._detect_tipo_pessoa_from_wizard(wizard_data)
                if tipo not in ("PF", "PJ"):
                    messages.error(self.request, "Tipo de pessoa inválido ou não informado.")
                    return redirect("clientes:clientes_list")

                pj_data = step_1_data.get("pj", {}) or {}
                pf_data = step_1_data.get("pf", {}) or {}
                dados_ident = pj_data if tipo == "PJ" else pf_data

                # Criar/obter cliente
                if editing_entity:
                    try:
                        cliente = Cliente.objects.get(pk=editing_entity, tenant=tenant)
                    except Cliente.DoesNotExist:
                        messages.error(self.request, "Cliente não encontrado.")
                        return redirect("clientes:clientes_list")
                else:
                    cliente = Cliente(tenant=tenant)

                cliente.tipo = tipo
                if dados_ident.get("email"):
                    cliente.email = dados_ident.get("email")
                if dados_ident.get("telefone"):
                    cliente.telefone = dados_ident.get("telefone")
                cliente.save()

                if tipo == "PF":
                    pf = getattr(cliente, "pessoafisica", None) or PessoaFisica(cliente=cliente)
                    if dados_ident.get("name") and not dados_ident.get("nome_completo"):
                        pf.nome_completo = dados_ident.get("name")
                    for field, value in dados_ident.items():
                        if hasattr(pf, field) and value is not None:
                            setattr(pf, field, value)
                    pf.save()
                else:
                    pj = getattr(cliente, "pessoajuridica", None) or PessoaJuridica(cliente=cliente)
                    if dados_ident.get("name") and not pj.nome_fantasia:
                        pj.nome_fantasia = dados_ident.get("name")
                    for field, value in dados_ident.items():
                        if hasattr(pj, field) and value is not None:
                            setattr(pj, field, value)
                    pj.save()

                # Processar Steps 2 e 3
                self._process_other_wizard_steps(cliente, wizard_data)

                # Limpar sessão e finalizar
                self.clear_wizard_data()
                messages.success(self.request, f'Cliente "{cliente.nome_display}" salvo com sucesso!')
                return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Erro ao salvar cliente: {e!s}")
            return redirect(self.success_url)

    def _process_other_wizard_steps(self, cliente, wizard_data):
        """Processa dados dos steps 2 (Endereço) e 3 (Contatos) alinhados ao CORE."""
        import json as _json

        # Endereço principal + adicionais
        try:
            step2 = (wizard_data.get("step_2") or {}).get("main") or {}
            if step2:
                cliente.cep = step2.get("cep") or cliente.cep
                cliente.logradouro = step2.get("logradouro") or cliente.logradouro
                cliente.numero = step2.get("numero") or cliente.numero
                cliente.complemento = step2.get("complemento") or cliente.complemento
                cliente.bairro = step2.get("bairro") or cliente.bairro
                cliente.cidade = step2.get("cidade") or cliente.cidade
                uf = step2.get("uf") or ""
                if uf:
                    cliente.estado = uf
                cliente.pais = step2.get("pais") or cliente.pais
                cliente.save()

                add_json = step2.get("additional_addresses_json") or "[]"
                try:
                    add_list = _json.loads(add_json) if isinstance(add_json, str) else (add_json or [])
                except Exception:
                    add_list = []
                if isinstance(add_list, list):
                    EnderecoAdicional.objects.filter(cliente=cliente).delete()
                    for ea in add_list:
                        try:
                            EnderecoAdicional.objects.create(
                                cliente=cliente,
                                tipo=ea.get("tipo") or "OUTRO",
                                logradouro=ea.get("logradouro") or "",
                                numero=ea.get("numero") or "",
                                complemento=ea.get("complemento") or "",
                                bairro=ea.get("bairro") or "",
                                cidade=ea.get("cidade") or "",
                                estado=(ea.get("uf") or ea.get("estado") or ""),
                                cep=ea.get("cep") or "",
                                pais=ea.get("pais") or "Brasil",
                                ponto_referencia=ea.get("ponto_referencia") or "",
                                principal=bool(ea.get("principal")),
                            )
                        except Exception:
                            continue
        except Exception:
            pass

        # Contatos principais do step 3
        try:
            step3 = (wizard_data.get("step_3") or {}).get("main") or {}
            if step3:
                email_p = step3.get("email_contato_principal")
                tel_p = step3.get("telefone_contato_principal")
                if email_p:
                    cliente.email = email_p
                if tel_p:
                    cliente.telefone = tel_p
                cliente.save()
        except Exception:
            pass

    def create_forms_for_step(self, current_step, editing_entity, data_source="POST"):
        """OVERRIDE CRÍTICO: Usa self.wizard_steps em vez de WIZARD_STEPS
        Mantém toda a lógica original, apenas muda a fonte dos steps
        """
        # Garantir que estamos usando nossos wizard_steps

        step_config = self.wizard_steps[current_step]
        form_classes = step_config["form_classes"]
        forms = {}

        # DEBUG reduzido: manter silencioso em produção

        for form_key, form_class in form_classes.items():
            # Para Steps 1–3 usamos apenas prefix/initial (não vinculamos instance, pois são forms do CORE/Tenant)
            prefix = form_key
            if data_source == "POST":
                form = form_class(self.request.POST, self.request.FILES, prefix=prefix)
            else:
                saved_data = self.get_wizard_data().get(f"step_{current_step}", {})
                initial_data = saved_data.get(form_key, {})
                form = form_class(initial=initial_data, prefix=prefix)
            forms[form_key] = form

        return forms

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """OVERRIDE NECESSÁRIO: Usa self.wizard_steps em vez de WIZARD_STEPS
        Mantém toda a lógica original, apenas muda a fonte dos steps
        """
        current_step = self.get_current_step()
        editing_tenant = self.get_editing_tenant()
        # Se estiver editando e ainda não há dados do wizard, carregar dados do cliente
        if editing_tenant and not self.get_wizard_data():
            with contextlib.suppress(Exception):
                self.load_cliente_data_to_wizard(editing_tenant)

        # Verificar se o step é válido - USA self.wizard_steps
        if current_step not in self.wizard_steps:
            messages.error(request, "Step inválido.")
            return redirect(self.success_url)

        # Obter configurações do step - USA self.wizard_steps
        step_config = self.wizard_steps[current_step]

        # Criar formulários usando método unificado
        forms = self.create_forms_for_step(current_step, editing_tenant, data_source="GET")

        context = self.get_context_data(
            forms=forms,
            current_step=current_step,
            step_config=step_config,
            editing_tenant=editing_tenant,
        )

        return render(request, step_config["template"], context)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """OVERRIDE NECESSÁRIO: Usa self.wizard_steps em vez de WIZARD_STEPS
        Mantém toda a lógica original, mas permite navegação livre entre steps.
        """
        current_step = self.get_current_step()
        editing_tenant = self.get_editing_tenant()

        # Verificar se o step é válido - USA self.wizard_steps
        if current_step not in self.wizard_steps:
            messages.error(request, "Step inválido.")
            return redirect(self.success_url)

        # Obter configurações do step - USA self.wizard_steps
        step_config = self.wizard_steps[current_step]

        # Criar formulários para validação
        forms = self.create_forms_for_step(current_step, editing_tenant, data_source="POST")

        # Intenção: finalizar ou apenas avançar
        is_finish_intent = "wizard_finish" in request.POST or current_step == len(self.wizard_steps)

        if is_finish_intent:
            # Validar todos os formulários ao finalizar
            all_valid = all(form.is_valid() for form in forms.values() if form)
            if all_valid:
                # Processar dados do step e salvar na sessão
                step_data = self.process_step_data(forms)
                self.set_wizard_data(current_step, step_data)
                # Último step - finalizar
                return self.finish_wizard()
            # Exibir erros e permanecer no step
            context = self.get_context_data(
                forms=forms,
                current_step=current_step,
                step_config=step_config,
                editing_tenant=editing_tenant,
            )
            return render(request, step_config["template"], context)

        # Navegação livre: salvar rascunho e avançar, mesmo com erros
        # 1) Dados válidos
        valid_step_data = self.process_step_data(forms)
        # 2) Rascunho dos inválidos (usa método herdado do core)
        draft_step_data = self.collect_step_draft_data(forms, current_step)
        # 3) Combinar (válidos sobrepõem rascunho)
        combined = dict(draft_step_data)
        combined.update(valid_step_data)
        self.set_wizard_data(current_step, combined)

        # Avançar para o próximo step
        if current_step < len(self.wizard_steps):
            self.set_current_step(current_step + 1)
        # Redirecionar para a mesma view (mantém PK quando edição)
        return redirect(request.path)

    def get_context_data(self, **kwargs):
        """OVERRIDE NECESSÁRIO: Usa self.wizard_steps para cálculos"""
        context = {}
        current_step = kwargs.get("current_step", self.get_current_step())
        step_config = kwargs.get("step_config", self.wizard_steps[current_step])

        # CRÍTICO: Garantir que os formulários sejam passados para o template
        forms = kwargs.get("forms")
        if forms:
            context["forms"] = forms
            # Para compatibilidade, também passar como 'form' se houver apenas 'main'
            if "main" in forms:
                context["form"] = forms["main"]

            # DEBUG: Adicionar informações sobre as classes dos forms
            context["debug_forms_info"] = {}
            for form_key, form in forms.items():
                context["debug_forms_info"][form_key] = {
                    "class_name": type(form).__name__,
                    "module_name": type(form).__module__,
                    "has_email": hasattr(form, "email"),
                    "email_label": getattr(form.email, "label", "N/A") if hasattr(form, "email") else "N/A",
                }

        # Dados básicos do wizard
        context.update(
            {
                "current_step": current_step,
                "total_steps": len(self.wizard_steps),
                "step_config": step_config,
                "steps_list": self.wizard_steps,
                "progress_percentage": (current_step / len(self.wizard_steps)) * 100,
                "can_go_previous": current_step > 1,
                "can_go_prev": current_step > 1,  # alias para template base
                "can_go_next": current_step < len(self.wizard_steps),
                "is_last_step": current_step == len(self.wizard_steps),
                # wizard_data completo para resumos no template de confirmação
                "wizard_data": self.get_wizard_data(),
                # Dados específicos do step
                "step_title": step_config.get("name", f"Step {current_step}"),
                "step_icon": step_config.get("icon", "user").replace("fas fa-", ""),
                "wizard_title": (
                    "Cadastro de Cliente" if not self.is_editing() else f"Editar Cliente - {self.get_editing_tenant()}"
                ),
                # Nomes de rotas para o template base (goto step)
                "wizard_goto_step_name": "clientes:cliente_wizard_goto_step",
                "wizard_goto_step_edit_name": "clientes:cliente_wizard_goto_step_edit",
                "wizard_goto_step_url_name": "clientes:cliente_wizard_goto_step",  # compat
                "wizard_list_url_name": "clientes:clientes_list",
                # Adicionar outros kwargs que possam ter sido passados
                **kwargs,
            },
        )

        return context

    def get_editing_tenant(self) -> Cliente | None:
        """ADAPTAÇÃO: Substitui get_editing_tenant por get_editing_cliente
        Usa a mesma lógica do wizard original mas para clientes
        """
        entity_pk = self.kwargs.get("pk")
        if entity_pk:
            try:
                # Para super admins, buscar em todos os tenants se não houver tenant selecionado
                current_tenant = getattr(self.request, "tenant", None)
                if self.request.user.is_superuser and not current_tenant:
                    return Cliente.objects.get(pk=entity_pk)
                # Para usuários normais ou super admins com tenant selecionado
                return Cliente.objects.filter(tenant=current_tenant).get(pk=entity_pk)
            except Cliente.DoesNotExist:
                return None
        return None

    def is_editing(self) -> bool:
        """Verifica se estamos editando um cliente"""
        return self.get_editing_tenant() is not None

    # Pré-carregamento dos dados do cliente no wizard (edição)
    def load_cliente_data_to_wizard(self, cliente: Cliente) -> None:
        data = {
            "step_1": {},
            "step_2": {"main": {}},
            "step_3": {"main": {}},
            "step_4": {"main": {}},
            "step_5": {"main": {}},
        }
        # Step 1: Identificação
        try:
            if cliente.tipo == "PJ" and hasattr(cliente, "pessoajuridica"):
                pj = cliente.pessoajuridica
                data["step_1"]["pj"] = {
                    "tipo_pessoa": "PJ",
                    "name": getattr(pj, "nome_fantasia", None) or getattr(pj, "razao_social", None),
                    "razao_social": getattr(pj, "razao_social", None),
                    "nome_fantasia": getattr(pj, "nome_fantasia", None),
                    "cnpj": getattr(pj, "cnpj", None),
                    "inscricao_estadual": getattr(pj, "inscricao_estadual", None),
                    "inscricao_municipal": getattr(pj, "inscricao_municipal", None),
                    "data_fundacao": getattr(pj, "data_fundacao", None),
                    "ramo_atividade": getattr(pj, "ramo_atividade", None),
                    "porte_empresa": getattr(pj, "porte_empresa", None),
                    "website": getattr(pj, "website", None),
                }
            elif cliente.tipo == "PF" and hasattr(cliente, "pessoafisica"):
                pf = cliente.pessoafisica
                data["step_1"]["pf"] = {
                    "tipo_pessoa": "PF",
                    "name": getattr(pf, "nome_completo", None),
                    "nome_completo": getattr(pf, "nome_completo", None),
                    "cpf": getattr(pf, "cpf", None),
                    "rg": getattr(pf, "rg", None),
                    "data_nascimento": getattr(pf, "data_nascimento", None),
                    "sexo": getattr(pf, "sexo", None),
                    "estado_civil": getattr(pf, "estado_civil", None),
                    "nacionalidade": getattr(pf, "nacionalidade", None),
                    "naturalidade": getattr(pf, "naturalidade", None),
                    "nome_mae": getattr(pf, "nome_mae", None),
                    "nome_pai": getattr(pf, "nome_pai", None),
                    "profissao": getattr(pf, "profissao", None),
                }
        except Exception:
            pass
        # Step 2: Endereço principal
        with contextlib.suppress(Exception):
            data["step_2"]["main"].update(
                {
                    "logradouro": getattr(cliente, "logradouro", None),
                    "numero": getattr(cliente, "numero", None),
                    "complemento": getattr(cliente, "complemento", None),
                    "bairro": getattr(cliente, "bairro", None),
                    "cidade": getattr(cliente, "cidade", None),
                    "uf": getattr(cliente, "estado", None),
                    "cep": getattr(cliente, "cep", None),
                },
            )
        # Step 3: Contatos básicos
        with contextlib.suppress(Exception):
            data["step_3"]["main"].update(
                {
                    "nome_contato_principal": getattr(cliente, "nome_contato_principal", None) or "",
                    "email_contato_principal": getattr(cliente, "email", None) or "",
                    "telefone_contato_principal": getattr(cliente, "telefone", None) or "",
                },
            )
        # Persistir sessão
        self.request.session["client_wizard_data"] = data
        self.request.session["client_wizard_step"] = 1
        self.request.session.modified = True


# Views auxiliares (mantendo compatibilidade com URLs existentes)
def cliente_wizard_create(request):
    """View function para criação via wizard"""
    return ClienteWizardView.as_view()(request)


def cliente_wizard_edit(request, pk):
    """View function para edição via wizard"""
    return ClienteWizardView.as_view()(request, pk=pk)


def cliente_wizard_goto_step(request, step, pk=None):
    """Permite navegar diretamente para um step específico no wizard de clientes."""
    try:
        step = int(step)
    except (ValueError, TypeError):
        messages.error(request, _("Step inválido."))
        return redirect("clientes:clientes_list")

    if step in CLIENTE_WIZARD_STEPS:
        request.session["client_wizard_step"] = step
        request.session.modified = True
        if pk:
            return redirect("clientes:clientes_update", pk=pk)
        return redirect("clientes:clientes_create")
    messages.error(request, _("Step inválido."))
    return redirect("clientes:clientes_list")


def cliente_wizard_goto_step_edit(request, pk, step):
    """Alias explícito para rota com pk obrigatório."""
    return cliente_wizard_goto_step(request, step=step, pk=pk)

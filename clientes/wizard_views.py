"""Wizard de clientes.

Reutiliza templates do CORE para os Steps 1-3 (Identificação, Endereços, Contatos),
mantendo chaves de sessão isoladas (``client_wizard_*``) e rotas de navegação direta
(`goto`). Inclui etapa de documentos (app ``documentos``) e confirmação própria.
"""

import contextlib
import json
import logging
from collections.abc import Mapping
from typing import Any

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from core.models import Tenant, TenantUser
from core.wizard_extensions import ClienteWizardMixin
from core.wizard_forms import TenantAddressWizardForm, TenantContactsWizardForm
from core.wizard_views import TenantCreationWizardView
from documentos.services import consolidate_wizard_temp_to_documents

from .models import Cliente, EnderecoAdicional, PessoaFisica, PessoaJuridica
from .wizard_forms import ClientePFIdentificationForm, ClientePJIdentificationForm, ClienteReviewWizardForm

try:  # Import seguro utilitário central
    from core.utils import get_current_tenant as _core_get_current_tenant
except (ImportError, RuntimeError):  # pragma: no cover
    _core_get_current_tenant = None


def get_current_tenant(request: HttpRequest) -> Tenant | None:
    """Obtem o tenant atual ou ``None`` se utilitário indisponível ou falhar."""
    if _core_get_current_tenant is None:
        return None
    try:
        return _core_get_current_tenant(request)
    except (AttributeError, RuntimeError):  # pragma: no cover
        return None


logger = logging.getLogger(__name__)

# Mapeamento de steps para clientes (reutilizando templates do CORE nos passos 1-3)
CLIENTE_WIZARD_STEPS: dict[int, dict[str, Any]] = {
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
        "form_classes": {},  # Sem formulário, a UI chama a API do app 'documentos'
        "template": "core/wizard/step_documents.html",  # Reutiliza o template do CORE
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
    """Wizard para clientes baseado no wizard de tenants.

    Herda a funcionalidade existente e customiza somente o necessário: nomes de
    steps, armazenamento de sessão isolado e consolidação de documentos.
    """

    # Configurações específicas de clientes
    success_url = reverse_lazy("clientes:clientes_list")

    # OVERRIDE FUNDAMENTAL: Definir os wizard steps específicos como propriedade da classe
    @property
    def wizard_steps(self) -> dict[int, dict[str, Any]]:
        """Retorna o mapeamento de steps específicos para clientes."""
        return CLIENTE_WIZARD_STEPS

    def dispatch(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        """Gerenciar acesso multi-tenant para o wizard de clientes."""
        if request.user.is_superuser:
            request.tenant = self.get_current_tenant(request)  # dinamicamente adicionado
            return super(TenantCreationWizardView, self).dispatch(request, *args, **kwargs)
        request.tenant = self.get_current_tenant(request)
        if not request.tenant:
            messages.error(request, _("Nenhuma empresa selecionada. Por favor, escolha uma para continuar."))
            return redirect("core:tenant_select")
        has_access = TenantUser.objects.filter(tenant=request.tenant, user=request.user).exists()
        if not has_access:
            messages.error(request, _("Você não tem permissão para acessar esta empresa."))
            return redirect("core:tenant_select")
        return super(TenantCreationWizardView, self).dispatch(request, *args, **kwargs)

    def get_current_tenant(self, request: HttpRequest) -> Tenant | None:  # -> Tenant | None (mantém flexível)
        """Retorna o tenant atual via utilitário central (ou ``None``)."""
        return get_current_tenant(request)

    def test_func(self) -> bool:
        """Verifica permissão de acesso (superusuário ou usuário com tenant)."""
        if self.request.user.is_superuser:
            return True
        return hasattr(self.request, "tenant") and self.request.tenant is not None

    def get_wizard_steps(self) -> dict[int, dict[str, Any]]:
        """Retorna steps (alias legado para compatibilidade com o core)."""
        return CLIENTE_WIZARD_STEPS

    def get_current_step(self) -> int:
        """Retorna step atual (sessão isolada)."""
        return self.request.session.get("client_wizard_step", 1)

    def set_current_step(self, step: int) -> None:
        """Atualiza o step atual (sessão isolada)."""
        self.request.session["client_wizard_step"] = step
        self.request.session.modified = True

    def get_wizard_data(self) -> dict[str, Any]:
        """Retorna dados persistidos do wizard (sessão isolada)."""
        return self.request.session.get("client_wizard_data", {})

    def set_wizard_data(self, step: int, data: dict[str, Any]) -> None:
        """Persistir dados de um step no armazenamento de sessão."""
        wizard_data = self.get_wizard_data()
        wizard_data[f"step_{step}"] = data
        self.request.session["client_wizard_data"] = wizard_data
        self.request.session.modified = True

    def clear_wizard_data(self) -> None:
        """Limpa dados/estado do wizard (inclui arquivos temporários)."""
        self.request.session.pop("client_wizard_step", None)
        self.request.session.pop("client_wizard_data", None)
        # Limpa eventuais arquivos temporários compatíveis com o core, se existirem
        with contextlib.suppress(Exception):
            self.clear_temp_files()
        self.request.session.modified = True

    def process_step_data(self, forms: dict[str, Any], _current_step: int) -> dict[str, Any]:
        """Extrai dados limpos dos formulários válidos do step."""
        # Reutiliza lógica simples de extração, sem migrações adicionais do core.
        step_data: dict[str, Any] = {}
        for form_key, form in forms.items():
            if form and hasattr(form, "is_valid") and form.is_valid():
                cleaned = getattr(form, "cleaned_data", {}).copy()
                step_data[form_key] = cleaned
        return step_data

    # ---------------------
    # Finalização / Persistência
    # ---------------------
    def finish_wizard(self) -> HttpResponse:
        """Finaliza o wizard criando/atualizando o cliente e aplicando steps."""
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
                tipo, dados_ident = self._extract_identificacao(step_1_data, wizard_data)
                if not dados_ident:
                    messages.error(self.request, "Dados de identificação insuficientes.")
                    return redirect("clientes:clientes_list")

                # Criar/obter cliente
                if editing_entity:
                    try:
                        cliente = Cliente.objects.get(pk=editing_entity, tenant=tenant)
                    except Cliente.DoesNotExist:
                        messages.error(self.request, "Cliente não encontrado.")
                        return redirect("clientes:clientes_list")
                else:
                    cliente = Cliente(tenant=tenant)

                self._apply_identificacao(cliente, tipo, dados_ident)
                self._apply_steps_2_3(cliente, wizard_data)
                # Consolidar documentos passando o objeto tenant corretamente
                self._consolidate_documents(cliente, tenant)

                # Limpar sessão e finalizar
                self.clear_wizard_data()
                messages.success(self.request, f'Cliente "{cliente.nome_display}" salvo com sucesso!')
                return redirect(self.success_url)
        except Exception as exc:  # ponto único para feedback ao usuário
            logger.exception("Erro inesperado ao finalizar wizard de cliente")
            messages.error(self.request, f"Erro ao salvar cliente: {exc!s}")
            return redirect(self.success_url)

    # ---------------------
    # Helpers refatorados (redução de complexidade)
    # ---------------------
    def _extract_identificacao(
        self,
        step_1_data: Mapping[str, Any],
        wizard_data: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        """Determina se PF/PJ e retorna dados de identificação selecionados."""
        tipo = self._detect_tipo_pessoa_from_wizard(wizard_data)
        pj_data = step_1_data.get("pj", {}) or {}
        pf_data = step_1_data.get("pf", {}) or {}
        dados_ident = pj_data if tipo == "PJ" else pf_data
        return tipo, dados_ident

    def _apply_identificacao(self, cliente: Cliente, tipo: str | None, dados_ident: Mapping[str, Any]) -> None:
        """Aplica dados de identificação no cliente e modelos relacionados."""
        cliente.tipo = tipo or cliente.tipo or "PF"
        cliente.email = dados_ident.get("email") or cliente.email
        cliente.telefone = dados_ident.get("telefone") or cliente.telefone
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

    def _apply_steps_2_3(self, cliente: Cliente, wizard_data: Mapping[str, Any]) -> None:
        """Aplica dados dos steps 2 (endereços) e 3 (contatos)."""
        self._apply_address_step(cliente, wizard_data.get("step_2", {}).get("main", {}))
        self._apply_contacts_step(cliente, wizard_data.get("step_3", {}).get("main", {}))

    def _apply_address_step(self, cliente: Cliente, step2: Mapping[str, Any]) -> None:
        if not step2:
            return
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
            add_list = json.loads(add_json) if isinstance(add_json, str) else (add_json or [])
        except (ValueError, TypeError):
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
                except Exception:  # noqa: BLE001
                    logger.debug("Falha ao criar endereço adicional (ignorado)")

    def _apply_contacts_step(self, cliente: Cliente, step3: Mapping[str, Any]) -> None:
        if not step3:
            return
        email_p = step3.get("email_contato_principal")
        tel_p = step3.get("telefone_contato_principal")
        if email_p:
            cliente.email = email_p
        if tel_p:
            cliente.telefone = tel_p
        cliente.save()

    def _consolidate_documents(self, cliente: Cliente, tenant: Tenant) -> None:
        """Consolida documentos temporários do wizard para o cliente."""
        try:
            consolidate_wizard_temp_to_documents(
                tenant=tenant,
                session_key=self.request.session.session_key,
                user=self.request.user,
            )
            logger.info("Documentos do wizard consolidados para o cliente %s", cliente.pk)
        except Exception:  # pragma: no cover - log e segue
            logger.exception(
                "Falha ao consolidar documentos do wizard para o cliente %s",
                cliente.pk,
            )

    def create_forms_for_step(
        self,
        current_step: int,
        _editing_entity: Cliente | None,
        data_source: str = "POST",
    ) -> dict[str, Any]:
        """Cria instâncias de formulários para o step atual (GET ou POST)."""
        # Garantir que estamos usando nossos wizard_steps

        step_config = self.wizard_steps[current_step]
        form_classes = step_config["form_classes"]
        forms = {}

        # DEBUG reduzido: manter silencioso em produção

        for form_key, form_class in form_classes.items():
            # Para Steps 1-3 usamos apenas prefix/initial (não vinculamos instance, pois são forms do CORE/Tenant)
            prefix = form_key
            if data_source == "POST":
                form = form_class(self.request.POST, self.request.FILES, prefix=prefix)
            else:
                saved_data = self.get_wizard_data().get(f"step_{current_step}", {})
                initial_data = saved_data.get(form_key, {})
                form = form_class(initial=initial_data, prefix=prefix)
            forms[form_key] = form

        return forms

    def get(self, request: HttpRequest, *_args: object, **_kwargs: object) -> HttpResponse:
        """Exibe o step atual (requisição GET)."""
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

    def post(self, request: HttpRequest, *_args: object, **_kwargs: object) -> HttpResponse:
        """Processa submissões (navegação/validação ou finalização)."""
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
            all_valid = all(form.is_valid() for form in forms.values() if form)
            if all_valid:
                step_data = self.process_step_data(forms, current_step)
                self.set_wizard_data(current_step, step_data)
                return self.finish_wizard()
            context = self.get_context_data(
                forms=forms,
                current_step=current_step,
                step_config=step_config,
                editing_tenant=editing_tenant,
            )
            return render(request, step_config["template"], context)

        valid_step_data = self.process_step_data(forms, current_step)
        draft_step_data = self._collect_step_draft_data(forms)
        combined = {**draft_step_data, **valid_step_data}
        self.set_wizard_data(current_step, combined)
        if current_step < len(self.wizard_steps):
            self.set_current_step(current_step + 1)
        return redirect(request.path)

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Montar contexto base para os templates do wizard."""
        context: dict[str, Any] = {}
        # Step atual
        current_step_raw = kwargs.get("current_step", self.get_current_step())
        if isinstance(current_step_raw, int):
            current_step = current_step_raw
        elif isinstance(current_step_raw, str) and current_step_raw.isdigit():
            current_step = int(current_step_raw)
        else:
            try:
                current_step = int(str(current_step_raw))
            except (TypeError, ValueError):
                current_step = self.get_current_step()

        # Configuração do step
        step_config = kwargs.get("step_config")
        if not isinstance(step_config, dict):  # fallback
            step_config = self.wizard_steps[current_step]

        # Formularios
        forms = kwargs.get("forms")
        if isinstance(forms, dict):
            context["forms"] = forms
            if "main" in forms:
                context["form"] = forms["main"]
            debug_info: dict[str, Any] = {}
            for fkey, fobj in forms.items():
                debug_info[fkey] = {
                    "class_name": type(fobj).__name__,
                    "module_name": type(fobj).__module__,
                    "has_email": hasattr(fobj, "email"),
                    "email_label": getattr(getattr(fobj, "email", None), "label", "N/A"),
                }
            context["debug_forms_info"] = debug_info

        context.update(
            {
                "current_step": current_step,
                "total_steps": len(self.wizard_steps),
                "step_config": step_config,
                "steps_list": self.wizard_steps,
                "progress_percentage": (current_step / len(self.wizard_steps)) * 100,
                "can_go_previous": current_step > 1,
                "can_go_prev": current_step > 1,
                "can_go_next": current_step < len(self.wizard_steps),
                "is_last_step": current_step == len(self.wizard_steps),
                "wizard_data": self.get_wizard_data(),
                "step_title": step_config.get("name", f"Step {current_step}"),
                "step_icon": step_config.get("icon", "user").replace("fas fa-", ""),
                "wizard_title": (
                    "Cadastro de Cliente" if not self.is_editing() else f"Editar Cliente - {self.get_editing_tenant()}"
                ),
                "wizard_goto_step_name": "clientes:cliente_wizard_goto_step",
                "wizard_goto_step_edit_name": "clientes:cliente_wizard_goto_step_edit",
                "wizard_goto_step_url_name": "clientes:cliente_wizard_goto_step",
                "wizard_list_url_name": "clientes:clientes_list",
            },
        )
        # kwargs adicionais (não sobrescreve chaves já definidas)
        for k, v in kwargs.items():
            context.setdefault(k, v)
        return context

    def get_editing_tenant(self) -> Cliente | None:
        """Retorna cliente em edição (compatibilidade com nome original do core)."""
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
        """Indica se há entidade em edição."""
        return self.get_editing_tenant() is not None

    # ---------------------
    # Draft helper local (evita dependência de mixin para testes)
    # ---------------------
    def _collect_step_draft_data(self, forms: dict[str, Any]) -> dict[str, dict[str, Any]]:
        draft: dict[str, dict[str, Any]] = {}
        post = getattr(self.request, "POST", {})
        for fkey, form in forms.items():
            fields = getattr(form, "fields", {})
            captured: dict[str, Any] = {}
            prefix = getattr(form, "prefix", None)
            for fname in fields:  # iterar diretamente evita uso desnecessário de .keys()
                pref = f"{prefix}-{fname}" if prefix else fname
                val = post.get(pref)
                if val is None:
                    val = post.get(fname)
                if fname == "tipo_pessoa" and val is None:
                    val = post.get("tipo")
                if val not in (None, ""):
                    captured[fname] = val
            if captured:
                draft[fkey] = captured
        return draft

    # Pré-carregamento dos dados do cliente no wizard (edição)
    def load_cliente_data_to_wizard(self, cliente: Cliente) -> None:
        """Carrega dados existentes do cliente para a sessão do wizard."""
        data: dict[str, Any] = {
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
        except (AttributeError, ValueError, TypeError):  # pragma: no cover - log baixo risco
            logger.debug(
                "Falha ao carregar identificação inicial do cliente %s",
                cliente.pk,
                exc_info=True,
            )
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
def cliente_wizard_create(request: HttpRequest) -> HttpResponse:
    """Criar cliente via wizard."""
    return ClienteWizardView.as_view()(request)


def cliente_wizard_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Editar cliente via wizard."""
    return ClienteWizardView.as_view()(request, pk=pk)


def cliente_wizard_goto_step(request: HttpRequest, step: int | str, pk: int | None = None) -> HttpResponse:
    """Navegar diretamente para um step específico do wizard de clientes."""
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


def cliente_wizard_goto_step_edit(request: HttpRequest, pk: int, step: int | str) -> HttpResponse:
    """Alias explícito para rota com pk obrigatório."""
    return cliente_wizard_goto_step(request, step=step, pk=pk)

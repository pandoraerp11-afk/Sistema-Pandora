"""Wizard de criação/edição de Fornecedor.

Objetivos da refatoração:
1. Alinhar o Step de Documentos ao modelo central (sem formulário local).
2. Remover exceções genéricas silenciosas e adicionar logging ou suppress explícito.
3. Reduzir complexidade ciclômica dos métodos `post`, `_process_other_steps` e
    `load_fornecedor_data_to_wizard` extraindo helpers e simplificando fluxos.
4. Adicionar docstrings e type hints para atender Ruff (ANN*, D10*).
5. Eliminar imports inline, acesso desnecessário a atributos privados e valores mágicos.
6. Manter compatibilidade com dados já persistidos em sessão de wizards anteriores.
"""

from __future__ import annotations

# Standard library
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

# Django
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:  # imports usados apenas para tipagem
    from collections.abc import Iterable

    from django.http import HttpRequest, HttpResponse
else:
    HttpRequest = "HttpRequest"  # type: ignore[assignment]
    HttpResponse = "HttpResponse"  # type: ignore[assignment]

from core.utils import get_current_tenant
from core.wizard_base import get_wizard_config
from core.wizard_extensions import FornecedorWizardMixin
from core.wizard_forms import (
    TenantAddressWizardForm,
)
from core.wizard_views import TenantCreationWizardView

from .models import (
    ContatoFornecedor,
    DadosBancariosFornecedor,
    EnderecoFornecedor,
    Fornecedor,
    FornecedorPF,
    FornecedorPJ,
)
from .wizard_forms import (
    FornecedorConfigWizardForm,
    FornecedorContactsExtendCoreForm,
    # FornecedorDocumentsWizardForm removido do fluxo: documentos agora são dinâmicos
    FornecedorPFIdentificationForm,
    FornecedorPJIdentificationForm,
    FornecedorReviewWizardForm,
)

logger = logging.getLogger(__name__)

STEP_IDENTIFICACAO: int = 1
STEP_ENDERECOS: int = 2
STEP_CONTATOS: int = 3
STEP_DOCUMENTOS: int = 4  # antes 5
STEP_CONFIGURACOES: int = 5  # antes 6 (agora incorpora dados bancários)
STEP_CONFIRMACAO: int = 6  # antes 7

FORNECEDOR_WIZARD_STEPS = {
    STEP_IDENTIFICACAO: {
        "name": "Identificação",
        "form_classes": {
            # Reutilizando os formulários completos do CORE (Tenant)
            "pj": FornecedorPJIdentificationForm,
            "pf": FornecedorPFIdentificationForm,
        },
        # Reutilizando o template compartilhado do CORE
        "template": "core/wizard/step_identification.html",
        "icon": "fas fa-truck",
        "description": "Dados básicos do fornecedor",
    },
    STEP_ENDERECOS: {
        "name": "Endereços",
        "form_classes": {
            "main": TenantAddressWizardForm,
        },
        "template": "core/wizard/step_address.html",
        "icon": "fas fa-map-marker-alt",
        "description": "Endereço principal e adicionais",
    },
    STEP_CONTATOS: {
        "name": "Contatos",
        "form_classes": {
            "main": FornecedorContactsExtendCoreForm,
        },
        "template": "fornecedores/wizard/step_contacts.html",
        "icon": "fas fa-phone",
        "description": "Contato principal e adicionais",
    },
    STEP_DOCUMENTOS: {
        "name": "Documentos",
        # Sem form local: gestão feita via módulo 'documentos' (JS + endpoints)
        "form_classes": {},
        "template": "fornecedores/wizard/step_documents.html",
        "icon": "fas fa-file-alt",
        "description": "Documentos gerenciados dinamicamente",
    },
    STEP_CONFIGURACOES: {
        "name": "Configurações",
        "form_classes": {
            "main": FornecedorConfigWizardForm,
        },
        "template": "fornecedores/wizard/step_config.html",
        "icon": "fas fa-gear",
        "description": "Preferências e tipo de fornecimento",
    },
    STEP_CONFIRMACAO: {
        "name": "Confirmação",
        "form_classes": {
            "main": FornecedorReviewWizardForm,
        },
        "template": "fornecedores/wizard/step_confirmation.html",
        "icon": "fas fa-check-circle",
        "description": "Revisão final",
    },
}


class FornecedorWizardView(FornecedorWizardMixin, TenantCreationWizardView):
    """Wizard específico de Fornecedor.

    Extende o wizard genérico de Tenant reutilizando templates e formulários do
    CORE onde possível. O passo de Documentos foi adaptado para não depender de
    formulário local: a gestão é 100% dinâmica via endpoints do app
    'documentos' e JavaScript no template.
    """

    success_url = reverse_lazy("fornecedores:fornecedores_list")

    # ------------------------------------------------------------------
    # Configuração de steps
    # ------------------------------------------------------------------
    @property
    def wizard_steps(self) -> dict[int, dict[str, Any]]:
        """Retorna o mapeamento de steps, preferindo configuração central."""
        try:
            cfg = get_wizard_config("fornecedor").get_wizard_steps()
        except (KeyError, AttributeError) as exc:  # Config não disponível ou inválida
            logger.warning(
                "Fallback para configuração local de steps do fornecedor (cfg inválida): %s",
                exc,
            )
            return FORNECEDOR_WIZARD_STEPS
        except (TypeError, ValueError):  # erros adicionais previsíveis
            logger.exception("Erro inesperado (tipo/valor) ao carregar configuração dinâmica do wizard de fornecedor")
            return FORNECEDOR_WIZARD_STEPS

        # Monta dicionário final incorporando overrides necessários
        return {
            STEP_IDENTIFICACAO: {
                **cfg.get(STEP_IDENTIFICACAO, {}),
                "name": "Identificação",
                "icon": "fas fa-truck",
                "description": "Dados básicos do fornecedor",
                "template": "core/wizard/step_identification.html",
                "form_classes": {
                    "pj": FornecedorPJIdentificationForm,
                    "pf": FornecedorPFIdentificationForm,
                },
            },
            STEP_ENDERECOS: {
                **cfg.get(STEP_ENDERECOS, {}),
                "name": "Endereços",
                "icon": "fas fa-map-marker-alt",
                "description": "Endereço principal e adicionais",
                "template": "core/wizard/step_address.html",
                "form_classes": {"main": TenantAddressWizardForm},
            },
            STEP_CONTATOS: {
                **cfg.get(STEP_CONTATOS, {}),
                "name": "Contatos",
                "icon": "fas fa-phone",
                "description": "Contato principal e adicionais",
                "template": "fornecedores/wizard/step_contacts.html",
                "form_classes": {"main": FornecedorContactsExtendCoreForm},
            },
            STEP_DOCUMENTOS: {
                **cfg.get(STEP_DOCUMENTOS, {}),
                "name": "Documentos",
                "icon": "fas fa-file-alt",
                "description": "Documentos (gerenciados externamente)",
                "template": "fornecedores/wizard/step_documents.html",
                "form_classes": {},  # Sem forms locais
            },
            STEP_CONFIGURACOES: {
                **cfg.get(STEP_CONFIGURACOES, {}),
                "name": "Configurações",
                "icon": "fas fa-gear",
                "description": "Preferências, tipo de fornecimento e dados bancários",
                "template": "fornecedores/wizard/step_config.html",
                "form_classes": {"main": FornecedorConfigWizardForm},
            },
            STEP_CONFIRMACAO: {
                **cfg.get(STEP_CONFIRMACAO, {}),
                "name": "Confirmação",
                "icon": "fas fa-check-circle",
                "description": "Revisão final",
                "template": "fornecedores/wizard/step_confirmation.html",
                "form_classes": {"main": FornecedorReviewWizardForm},
            },
        }

    def test_func(self) -> bool:
        """Restringe acesso ao wizard.

        Permite superuser ou usuário vinculado a um tenant atual.
        """
        return bool(self.request.user.is_superuser or get_current_tenant(self.request))

    def get_current_step(self) -> int:
        """Obtém step atual isolado por chave específica de sessão."""
        return int(self.request.session.get("supplier_wizard_step", STEP_IDENTIFICACAO))

    def set_current_step(self, step: int) -> None:
        """Atualiza step atual na sessão."""
        self.request.session["supplier_wizard_step"] = int(step)
        self.request.session.modified = True

    def get_wizard_data(self) -> dict[str, Any]:
        """Retorna snapshot de dados do wizard persistidos na sessão."""
        raw = self.request.session.get("supplier_wizard_data", {})
        return raw if isinstance(raw, dict) else {}

    def set_wizard_data(self, step: int, data: dict[str, Any]) -> None:
        """Persistir dados (válidos e rascunho) de um step na sessão."""
        wizard_data = self.get_wizard_data()
        wizard_data[f"step_{int(step)}"] = data
        self.request.session["supplier_wizard_data"] = wizard_data
        self.request.session.modified = True

    def clear_wizard_data(self) -> None:
        """Limpa sessão relacionada ao wizard de fornecedores."""
        for key in ("supplier_wizard_step", "supplier_wizard_data"):
            self.request.session.pop(key, None)
        self.request.session.modified = True

    def get_editing_tenant(self) -> Fornecedor | None:
        """Retorna fornecedor em edição (ou None)."""
        entity_pk = self.kwargs.get("pk")
        if not entity_pk:
            return None
        tenant = get_current_tenant(self.request)
        qs = Fornecedor.objects
        if not self.request.user.is_superuser and tenant:
            qs = qs.filter(tenant=tenant)
        with contextlib.suppress(Fornecedor.DoesNotExist):
            return qs.get(pk=entity_pk)
        return None

    def create_forms_for_step(
        self,
        current_step: int,
        editing_entity: Fornecedor | None,
        data_source: str = "POST",
    ) -> dict[str, Any]:
        """Instancia forms para o step.

        Step de Documentos não gera formulários (retorna dicionário vazio).
        """
        del editing_entity  # não utilizado diretamente aqui (mantido pela assinatura homogênea)
        step_config = self.wizard_steps[current_step]
        form_classes: dict[str, Any] = step_config.get("form_classes", {})
        forms: dict[str, Any] = {}
        if not form_classes:
            return forms
        saved_data = self.get_wizard_data().get(f"step_{current_step}", {}) if data_source != "POST" else {}
        for form_key, form_class in form_classes.items():
            if data_source == "POST":
                forms[form_key] = form_class(self.request.POST, self.request.FILES, prefix=form_key)
            else:
                initial_data = saved_data.get(form_key, {})
                forms[form_key] = form_class(initial=initial_data, prefix=form_key)
        return forms

    def process_step_data(self, forms: dict[str, Any], current_step: int) -> dict[str, Any]:
        """Coleta cleaned_data somente de forms válidos deste step.

        Mantém compatibilidade com assinatura da classe base em core.wizard_views.
        O parâmetro current_step é usado para permitir transformações futuras
        específicas por step (no momento não há transformação adicional).
        """
        del current_step  # não utilizado agora
        step_data: dict[str, Any] = {}
        for form_key, form in forms.items():
            if hasattr(form, "is_valid") and form.is_valid():
                cleaned = getattr(form, "cleaned_data", {}).copy()
                step_data[form_key] = cleaned
        return step_data

    # ------------------------------------------------------------------
    # Métodos auxiliares adicionados (eram referenciados mas não definidos)
    # ------------------------------------------------------------------
    def _persist_step_progress(self, forms: dict[str, Any], current_step: int) -> None:
        """Persist progress of the step combining cleaned and draft data.

        If the form is valid store cleaned_data; otherwise keep raw draft to
        avoid losing user input when validation fails.
        """
        cleaned = self.process_step_data(forms, current_step)
        draft = self.collect_step_draft_data(forms, current_step)
        merged: dict[str, Any] = {}
        # prioriza cleaned, mas mantém chaves de draft que não validaram
        merged.update(draft)
        merged.update(cleaned)
        self.set_wizard_data(current_step, merged)

    def _handle_prev_navigation(self, editing_entity: Fornecedor | None, current_step: int) -> HttpResponse:
        """Go back one step in the wizard preserving current data."""
        del editing_entity  # não utilizado agora, reservado para lógica futura
        if current_step > 1:
            self.set_current_step(current_step - 1)
        return redirect(self.request.path)

    def _handle_finish_intent(
        self,
        request: HttpRequest,
        forms: dict[str, Any],
        current_step: int,
        editing_entity: Fornecedor | None,
    ) -> HttpResponse:
        """Validate last step and finish wizard if all forms are valid."""
        # Persistir progresso antes de finalizar (inclui dados parcialmente válidos)
        self._persist_step_progress(forms, current_step)
        # Se houver forms e algum inválido, re-renderiza para correção
        invalid = [f for f in forms.values() if hasattr(f, "is_valid") and not f.is_valid()]
        if invalid:
            step_cfg = self.wizard_steps[current_step]
            context = self.get_context_data(
                forms=forms,
                current_step=current_step,
                step_config=step_cfg,
                editing_tenant=editing_entity,
            )
            return render(request, step_cfg["template"], context)
        return self.finish_wizard()

    # =====================
    # Draft helper (equivalente ao usado em clientes / versão pré-refatoração)
    # Mantém regras de negócio intactas: apenas captura valores brutos dos campos
    # para preservar o que o usuário digitou mesmo que o form não valide tudo ainda.
    # =====================
    def collect_step_draft_data(
        self,
        forms: dict[str, Any],
        current_step: int,  # noqa: ARG002 - reservado para futuros usos / paridade de assinatura
    ) -> dict[str, dict[str, Any]]:
        """Extrai valores crus submetidos (mesmo inválidos) para rascunho."""
        draft: dict[str, dict[str, Any]] = {}
        post = getattr(self.request, "POST", {})
        for fkey, form in forms.items():
            captured: dict[str, Any] = {}
            fields_obj = getattr(form, "fields", {})
            fields: Iterable[str] = fields_obj.keys() if hasattr(fields_obj, "keys") else []
            prefix = getattr(form, "prefix", None)
            for fname in fields:
                # Mantém compatibilidade com prefixos usados nos templates
                pref_name = f"{prefix}-{fname}" if prefix else fname
                val = post.get(pref_name, post.get(fname))
                if fname == "tipo_pessoa" and val is None:
                    val = post.get("tipo")  # fallback legado
                if val not in (None, ""):
                    captured[fname] = val
            if captured:
                draft[fkey] = captured
        return draft

    def get(self, request: HttpRequest, *_args: object, **_kwargs: object) -> HttpResponse:
        """Exibir o formulário do step atual (requisição GET)."""
        with contextlib.suppress(AttributeError, KeyError, ValueError):  # adaptação não crítica
            self.adapt_wizard_for_entity()
        current_step = self.get_current_step()
        editing_entity = self.get_editing_tenant()
        if editing_entity and not self.get_wizard_data():  # preload para edição
            self.load_fornecedor_data_to_wizard(editing_entity)
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        step_cfg = self.wizard_steps[current_step]
        forms = self.create_forms_for_step(current_step, editing_entity, data_source="GET")
        context = self.get_context_data(
            forms=forms,
            current_step=current_step,
            step_config=step_cfg,
            editing_tenant=editing_entity,
        )
        return render(request, step_cfg["template"], context)

    def post(self, request: HttpRequest, *_args: object, **_kwargs: object) -> HttpResponse:
        """Processar submissão: avançar, voltar ou finalizar wizard."""
        current_step = self.get_current_step()
        editing_entity = self.get_editing_tenant()
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        if "wizard_prev" in request.POST:
            return self._handle_prev_navigation(editing_entity, current_step)
        forms = self.create_forms_for_step(current_step, editing_entity, data_source="POST")
        finish_intent = "wizard_finish" in request.POST or current_step == len(self.wizard_steps)
        if finish_intent:
            return self._handle_finish_intent(request, forms, current_step, editing_entity)
        self._persist_step_progress(forms, current_step)
        if current_step < len(self.wizard_steps):
            self.set_current_step(current_step + 1)
        return redirect(request.path)

    def finish_wizard(self) -> HttpResponse:
        """Criar ou atualizar o fornecedor consolidando dados dos steps."""
        wizard_data = self.get_wizard_data() or {}
        step1 = wizard_data.get("step_1", {}) or {}
        tenant = get_current_tenant(self.request)
        if not tenant:
            messages.error(self.request, _("Nenhuma empresa selecionada."))
            return redirect(self.success_url)
        tipo = self._detect_tipo_pessoa_from_wizard(wizard_data)
        if tipo not in ("PJ", "PF"):
            messages.error(
                self.request,
                _("Selecione Pessoa Física ou Jurídica e preencha os dados obrigatórios."),
            )
            return redirect(self.success_url)
        pj = step1.get("pj", {}) or {}
        pf = step1.get("pf", {}) or {}
        try:
            with transaction.atomic():
                editing = self.get_editing_tenant()
                fornecedor = editing or Fornecedor(tenant=tenant)
                fornecedor.tipo_pessoa = tipo
                fornecedor.tenant = tenant
                fornecedor.save()
                if tipo == "PF":
                    self._apply_pf_data(fornecedor, pf)
                else:
                    self._apply_pj_data(fornecedor, pj)
                self._process_other_steps(fornecedor, wizard_data)
                self.clear_wizard_data()
                messages.success(self.request, _("Fornecedor salvo com sucesso."))
                return redirect(reverse("fornecedores:fornecedor_detail", kwargs={"pk": fornecedor.pk}))
        except (IntegrityError, DatabaseError, ValidationError):
            logger.exception("Erro de banco/validação ao salvar fornecedor")
            messages.error(self.request, _("Erro ao salvar fornecedor."))
            return redirect(self.success_url)

    # ------------------------------------------------------------------
    # Persistência de outros steps
    # ------------------------------------------------------------------
    def _process_other_steps(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]) -> None:
        """Aplicar dados dos steps (endereços, contatos, config+bancário)."""
        self._apply_addresses(fornecedor, wizard_data)
        self._apply_contacts(fornecedor, wizard_data)
        self._apply_config(fornecedor, wizard_data)  # inclui bancário

    # ---------------- Helpers PF/PJ -----------------
    def _apply_pf_data(self, fornecedor: Fornecedor, pf: dict[str, Any]) -> None:
        """Aplicar dados de pessoa física ao relacionamento."""
        pf_obj = getattr(fornecedor, "pessoafisica", None) or FornecedorPF(fornecedor=fornecedor)
        mapping_pf = {
            "name": "nome_completo",
            "cpf": "cpf",
            "rg": "rg",
            "data_nascimento": "data_nascimento",
            "sexo": "sexo",
            "estado_civil": "estado_civil",
            "nacionalidade": "nacionalidade",
            "naturalidade": "naturalidade",
            "nome_mae": "nome_mae",
            "nome_pai": "nome_pai",
            "profissao": "profissao",
            "escolaridade": "escolaridade",
        }
        for src, dst in mapping_pf.items():
            if src in pf and hasattr(pf_obj, dst):
                setattr(pf_obj, dst, pf.get(src))
        pf_obj.save()

    def _apply_pj_data(self, fornecedor: Fornecedor, pj: dict[str, Any]) -> None:
        """Aplicar dados de pessoa jurídica ao relacionamento."""
        pj_obj = getattr(fornecedor, "pessoajuridica", None) or FornecedorPJ(fornecedor=fornecedor)
        mapping_pj = {
            "name": "nome_fantasia",
            "razao_social": "razao_social",
            "cnpj": "cnpj",
            "inscricao_estadual": "inscricao_estadual",
            "inscricao_municipal": "inscricao_municipal",
            "data_fundacao": "data_fundacao",
            "ramo_atividade": "ramo_atividade",
            "porte_empresa": "porte_empresa",
            "cnae_principal": "cnae_principal",
            "regime_tributario": "regime_tributario",
        }
        for src, dst in mapping_pj.items():
            if src in pj and hasattr(pj_obj, dst):
                setattr(pj_obj, dst, pj.get(src))
        pj_obj.save()

    # ---------------- Helpers Steps -----------------
    def _apply_addresses(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]) -> None:
        step2 = wizard_data.get("step_2", {}).get("main", {})
        if not step2:
            return
        addr, _ = EnderecoFornecedor.objects.get_or_create(
            fornecedor=fornecedor,
            logradouro=step2.get("logradouro", ""),
            numero=step2.get("numero", ""),
            defaults={
                "complemento": step2.get("complemento") or "",
                "bairro": step2.get("bairro") or "",
                "cidade": step2.get("cidade") or "",
                "estado": step2.get("uf") or "",
                "cep": step2.get("cep") or "",
            },
        )
        raw_add = (step2.get("additional_addresses_json") or "").strip()
        if raw_add:
            with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
                parsed = json.loads(raw_add)
                EnderecoFornecedor.objects.filter(fornecedor=fornecedor).exclude(pk=addr.pk).delete()
                for it in parsed[:50]:
                    if isinstance(it, dict):
                        EnderecoFornecedor.objects.create(
                            fornecedor=fornecedor,
                            logradouro=it.get("logradouro", "")[:255],
                            numero=it.get("numero", "")[:20],
                            complemento=(it.get("complemento") or "")[:100],
                            bairro=(it.get("bairro") or "")[:100],
                            cidade=(it.get("cidade") or "")[:100],
                            estado=(it.get("uf") or "")[:2],
                            cep=(it.get("cep") or "")[:9],
                        )

    def _apply_contacts(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]) -> None:
        step3 = wizard_data.get("step_3", {}).get("main", {})
        if not step3:
            return
        self._apply_contacts_principal(fornecedor, step3)
        self._apply_contacts_departamentais(fornecedor, step3)
        self._apply_contacts_vendedores(fornecedor, step3)
        self._apply_contacts_funcionarios(fornecedor, step3)
        self._apply_contacts_pj_social(fornecedor, step3)

    def _apply_contacts_principal(self, fornecedor: Fornecedor, step3: dict[str, Any]) -> None:
        nome = step3.get("nome_contato_principal") or "-"
        email = step3.get("email_contato_principal") or ""
        telefone = step3.get("telefone_contato_principal") or ""
        cargo = step3.get("cargo_contato_principal") or ""
        if nome or email or telefone:
            ContatoFornecedor.objects.update_or_create(
                fornecedor=fornecedor,
                nome=nome,
                defaults={"email": email, "telefone": telefone, "cargo": cargo},
            )

    def _apply_contacts_departamentais(self, fornecedor: Fornecedor, step3: dict[str, Any]) -> None:
        nome_resp_com = step3.get("nome_responsavel_comercial")
        if nome_resp_com:
            ContatoFornecedor.objects.update_or_create(
                fornecedor=fornecedor,
                nome=(nome_resp_com or "")[:100],
                defaults={
                    "email": (step3.get("email_comercial") or "")[:255],
                    "telefone": (step3.get("telefone_comercial") or "")[:20],
                    "cargo": (step3.get("cargo_responsavel_comercial") or "Comercial")[:100],
                },
            )
        nome_resp_fin = step3.get("nome_responsavel_financeiro")
        if nome_resp_fin:
            ContatoFornecedor.objects.update_or_create(
                fornecedor=fornecedor,
                nome=(nome_resp_fin or "")[:100],
                defaults={
                    "email": (step3.get("email_financeiro") or "")[:255],
                    "telefone": (step3.get("telefone_financeiro") or "")[:20],
                    "cargo": (step3.get("cargo_responsavel_financeiro") or "Financeiro")[:100],
                },
            )

    def _apply_contacts_vendedores(self, fornecedor: Fornecedor, step3: dict[str, Any]) -> None:
        raw_vendors = (step3.get("additional_vendors_json") or "").strip()
        if not raw_vendors:
            return
        with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
            parsed = json.loads(raw_vendors)
            ContatoFornecedor.objects.filter(fornecedor=fornecedor, cargo__iexact="Vendedor").delete()
            for it in parsed[:100]:
                if isinstance(it, dict):
                    ContatoFornecedor.objects.create(
                        fornecedor=fornecedor,
                        nome=(it.get("nome") or "-")[:100],
                        email=(it.get("email") or "")[:255],
                        telefone=(it.get("telefone") or "")[:20],
                        cargo="Vendedor",
                    )

    def _apply_contacts_funcionarios(self, fornecedor: Fornecedor, step3: dict[str, Any]) -> None:
        raw_emps = (step3.get("additional_employees_json") or "").strip()
        if not raw_emps:
            return
        with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
            parsed = json.loads(raw_emps)
            preserved = ["Vendedor", "Comercial", "Financeiro"]
            ContatoFornecedor.objects.filter(fornecedor=fornecedor).exclude(cargo__in=preserved).delete()
            for it in parsed[:200]:
                if isinstance(it, dict):
                    ContatoFornecedor.objects.create(
                        fornecedor=fornecedor,
                        nome=(it.get("nome") or "-")[:100],
                        email=(it.get("email") or "")[:255],
                        telefone=(it.get("telefone") or "")[:20],
                        cargo=(it.get("cargo") or "-")[:100],
                    )

    def _apply_contacts_pj_social(self, fornecedor: Fornecedor, step3: dict[str, Any]) -> None:
        if fornecedor.tipo_pessoa != "PJ" or not hasattr(fornecedor, "pessoajuridica"):
            return
        with contextlib.suppress(AttributeError, ValueError):
            pj_obj = fornecedor.pessoajuridica
            pj_obj.website = (step3.get("website") or "")[:255]
            socials: list[str] = []
            for key in ("linkedin", "instagram", "facebook"):
                val = (step3.get(key) or "").strip()
                if val:
                    socials.append(f"{key}:{val}")
            pj_obj.redes_sociais = " | ".join(socials)[:255] if socials else (pj_obj.redes_sociais or "")
            pj_obj.save(update_fields=["website", "redes_sociais"])

    def _apply_banking(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]) -> None:
        step4 = wizard_data.get("step_4", {}).get("main", {})
        if not step4:
            return
        if step4.get("banco") and step4.get("agencia") and step4.get("conta"):
            DadosBancariosFornecedor.objects.update_or_create(
                fornecedor=fornecedor,
                banco=step4.get("banco"),
                agencia=step4.get("agencia"),
                conta=step4.get("conta"),
                defaults={
                    "tipo_chave_pix": step4.get("tipo_chave_pix") or "",
                    "chave_pix": step4.get("chave_pix") or "",
                },
            )
        raw_bank = (step4.get("additional_bank_json") or "").strip()
        if raw_bank:
            with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
                parsed = json.loads(raw_bank)
                for it in parsed[:50]:
                    if isinstance(it, dict) and it.get("banco") and it.get("agencia") and it.get("conta"):
                        DadosBancariosFornecedor.objects.get_or_create(
                            fornecedor=fornecedor,
                            banco=(it.get("banco") or "")[:100],
                            agencia=(it.get("agencia") or "")[:20],
                            conta=(it.get("conta") or "")[:20],
                            defaults={
                                "tipo_chave_pix": (it.get("tipo_chave_pix") or "")[:50],
                                "chave_pix": (it.get("chave_pix") or "")[:255],
                            },
                        )

    def _apply_config(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]) -> None:
        step_cfg = wizard_data.get("step_5", {}).get("main", {}) or wizard_data.get("step_6", {}).get("main", {})
        step6 = step_cfg  # alias para legados locais
        if not step6:
            return
        tipo_forn = step6.get("tipo_fornecimento") or None
        if tipo_forn in dict(Fornecedor.TIPO_FORNECIMENTO_CHOICES):
            fornecedor.tipo_fornecimento = tipo_forn
        fornecedor.prazo_pagamento_dias = step6.get("prazo_pagamento_dias") or None
        fornecedor.pedido_minimo = step6.get("pedido_minimo") or None
        fornecedor.prazo_medio_entrega_dias = step6.get("prazo_medio_entrega_dias") or None
        fornecedor.save(
            update_fields=[
                "tipo_fornecimento",
                "prazo_pagamento_dias",
                "pedido_minimo",
                "prazo_medio_entrega_dias",
            ],
        )
        linhas = step6.get("linhas_fornecidas")
        if isinstance(linhas, list):
            with contextlib.suppress(AttributeError):
                fornecedor.linhas_fornecidas.set(linhas)

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """Build extended context for supplier wizard templates."""
        kw: dict[str, object] = kwargs  # tipo mais específico p/ mypy
        context = super(TenantCreationWizardView, self).get_context_data(**kw)
        current_step_obj = kw.get("current_step", self.get_current_step())
        current_step = current_step_obj if isinstance(current_step_obj, int) else self.get_current_step()
        step_cfg_obj = kw.get("step_config")
        step_config: dict[str, Any] = (
            step_cfg_obj if isinstance(step_cfg_obj, dict) else self.wizard_steps.get(current_step, {})
        )
        editing_entity = kw.get("editing_tenant", self.get_editing_tenant())
        if not isinstance(editing_entity, (Fornecedor, type(None))):  # sanity
            editing_entity = self.get_editing_tenant()
        forms_dict = kw.get("forms")
        if isinstance(forms_dict, dict) and forms_dict:
            context["forms"] = forms_dict
            if len(forms_dict) == 1 and "main" in forms_dict:
                context["form"] = forms_dict["main"]

        total_steps = len(self.wizard_steps)
        wizard_data = self.get_wizard_data() or {}
        # Determinar alguns valores de preview
        preview_name = "Novo Fornecedor"
        tipo = self._detect_tipo_pessoa_from_wizard(wizard_data)
        email = None
        cidade = None
        uf = None
        step1 = wizard_data.get("step_1", {})
        pf = step1.get("pf", {}) if isinstance(step1.get("pf", {}), dict) else {}
        pj = step1.get("pj", {}) if isinstance(step1.get("pj", {}), dict) else {}
        if tipo == "PJ":
            preview_name = pj.get("name") or pj.get("nome_fantasia") or pj.get("razao_social") or preview_name
        elif tipo == "PF":
            preview_name = pf.get("name") or pf.get("nome_completo") or preview_name
        step3 = wizard_data.get("step_3", {}).get("main", {})
        email = step3.get("email_contato_principal")
        step2 = wizard_data.get("step_2", {}).get("main", {})
        cidade = step2.get("cidade")
        uf = step2.get("uf")

        context.update(
            {
                "wizard_title": (
                    f"Editar Fornecedor - {editing_entity}" if editing_entity else "Cadastro de Novo Fornecedor"
                ),
                "wizard_subtitle": "Configure um novo fornecedor no sistema.",
                "current_step": current_step,
                "total_steps": total_steps,
                "step_config": step_config,
                "steps_list": self.wizard_steps,
                "progress_percentage": (current_step / total_steps) * 100,
                "can_go_prev": current_step > 1,
                "can_go_previous": current_step > 1,
                "can_go_next": current_step < total_steps,
                "is_last_step": current_step == total_steps,
                "is_editing": editing_entity is not None,
                "editing_tenant": editing_entity,
                "step_title": (
                    step_config.get("name", f"Passo {current_step}") if step_config else f"Passo {current_step}"
                ),
                "step_icon": (step_config.get("icon", "fas fa-truck") if step_config else "fas fa-truck").replace(
                    "fas fa-",
                    "",
                ),
                "wizard_data": wizard_data,
                "preview_card_title": "Preview do Fornecedor",
                "preview_name": preview_name,
                "preview_subtext": "Complete os dados do fornecedor",
                "preview_type_text": (
                    "Pessoa Jurídica" if tipo == "PJ" else ("Pessoa Física" if tipo == "PF" else "Tipo não definido")
                ),
                "preview_email": email or "E-mail não informado",
                "preview_location": (f"{cidade}/{uf}" if cidade and uf else "Endereço não informado"),
                "preview_primary_badge": "Empresa" if tipo == "PJ" else "Pessoa",
                "preview_secondary_badge": "Em edição" if editing_entity else "Em criação",
                # Parametrização de rotas para o template base
                "wizard_goto_step_name": "fornecedores:fornecedor_wizard_goto_step",
                "wizard_goto_step_edit_name": "fornecedores:fornecedor_wizard_goto_step_edit",
                "wizard_goto_step_url_name": "fornecedores:fornecedor_wizard_goto_step",
                "wizard_list_url_name": "fornecedores:fornecedores_list",
            },
        )

        # Contexto adicional para o Step 5 (Documentos): listar tipos e histórico quando em edição
        if current_step == STEP_DOCUMENTOS and editing_entity:
            context["fornecedor"] = editing_entity  # utilizado pelo template
        return context

    def load_fornecedor_data_to_wizard(self, fornecedor: Fornecedor) -> None:
        """Precarregar dados do fornecedor para modo edição."""
        data = self._init_wizard_data_dict()
        self._preload_step1_identificacao(fornecedor, data)
        self._preload_step2_enderecos(fornecedor, data)
        self._preload_step3_contatos(fornecedor, data)
        self._preload_step5_config(fornecedor, data)
        self.request.session["supplier_wizard_data"] = data
        self.request.session["supplier_wizard_step"] = 1
        self.request.session.modified = True

    # -------- Preload helpers --------
    def _init_wizard_data_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            "step_1": {},
            "step_2": {"main": {}},
            "step_3": {"main": {}},
            "step_4": {"main": {}},  # documentos (sem form)
            "step_5": {"main": {}},  # config + dados bancários
            "step_6": {"main": {}},  # confirmação
        }

    def _preload_step1_identificacao(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        data["step_1"].setdefault("main", {})["tipo_pessoa"] = getattr(fornecedor, "tipo_pessoa", "PJ")
        if fornecedor.tipo_pessoa == "PJ" and hasattr(fornecedor, "pessoajuridica"):
            pj = fornecedor.pessoajuridica
            data["step_1"]["pj"] = {
                "tipo_pessoa": "PJ",
                "name": pj.nome_fantasia,
                "razao_social": pj.razao_social,
                "nome_fantasia": pj.nome_fantasia,
                "cnpj": pj.cnpj,
                "inscricao_estadual": pj.inscricao_estadual,
                "inscricao_municipal": pj.inscricao_municipal,
                "data_fundacao": pj.data_fundacao,
                "ramo_atividade": pj.ramo_atividade,
                "porte_empresa": pj.porte_empresa,
                "cnae_principal": pj.cnae_principal,
                "regime_tributario": getattr(pj, "regime_tributario", None),
            }
        elif fornecedor.tipo_pessoa == "PF" and hasattr(fornecedor, "pessoafisica"):
            pf = fornecedor.pessoafisica
            data["step_1"]["pf"] = {
                "tipo_pessoa": "PF",
                "name": pf.nome_completo,
                "nome_completo": pf.nome_completo,
                "cpf": pf.cpf,
                "rg": pf.rg,
                "data_nascimento": pf.data_nascimento,
                "sexo": pf.sexo,
                "estado_civil": pf.estado_civil,
                "nacionalidade": pf.nacionalidade,
                "naturalidade": pf.naturalidade,
                "nome_mae": pf.nome_mae,
                "nome_pai": pf.nome_pai,
                "profissao": pf.profissao,
            }

    def _preload_step2_enderecos(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        end = fornecedor.enderecos.first()
        if not end:
            return
        data["step_2"]["main"].update(
            {
                "logradouro": end.logradouro,
                "numero": end.numero,
                "complemento": end.complemento,
                "bairro": end.bairro,
                "cidade": end.cidade,
                "uf": end.estado,
                "cep": end.cep,
            },
        )

    def _preload_step3_contatos(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        self._preload_contact_principal(fornecedor, data)
        self._preload_contact_departamentais(fornecedor, data)
        self._preload_contact_lists(fornecedor, data)
        self._preload_contact_pj_social(fornecedor, data)

    def _preload_contact_principal(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        cont = fornecedor.contatos.first()
        if not cont:
            return
        data["step_3"]["main"].update(
            {
                "nome_contato_principal": cont.nome,
                "email_contato_principal": cont.email,
                "telefone_contato_principal": cont.telefone,
                "cargo_contato_principal": cont.cargo,
            },
        )

    def _preload_contact_departamentais(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        cont_com = fornecedor.contatos.filter(cargo__icontains="Comercial").first()
        if cont_com:
            data["step_3"]["main"].update(
                {
                    "nome_responsavel_comercial": cont_com.nome,
                    "email_comercial": cont_com.email,
                    "telefone_comercial": cont_com.telefone,
                    "cargo_responsavel_comercial": cont_com.cargo,
                },
            )
        cont_fin = fornecedor.contatos.filter(cargo__icontains="Financeiro").first()
        if cont_fin:
            data["step_3"]["main"].update(
                {
                    "nome_responsavel_financeiro": cont_fin.nome,
                    "email_financeiro": cont_fin.email,
                    "telefone_financeiro": cont_fin.telefone,
                    "cargo_responsavel_financeiro": cont_fin.cargo,
                },
            )

    def _preload_contact_lists(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        vendors = fornecedor.contatos.filter(cargo__iexact="Vendedor").values("nome", "email", "telefone")
        if vendors:
            data["step_3"]["main"]["additional_vendors_json"] = json.dumps(list(vendors), ensure_ascii=False)
        preserved = ["Vendedor", "Comercial", "Financeiro"]
        emps = fornecedor.contatos.exclude(cargo__in=preserved).values("nome", "email", "telefone", "cargo")
        if emps:
            data["step_3"]["main"]["additional_employees_json"] = json.dumps(list(emps), ensure_ascii=False)

    def _preload_contact_pj_social(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        if fornecedor.tipo_pessoa != "PJ" or not hasattr(fornecedor, "pessoajuridica"):
            return
        pj = fornecedor.pessoajuridica
        if getattr(pj, "website", None):
            data["step_3"]["main"]["website"] = pj.website
        if getattr(pj, "redes_sociais", None):
            parts = [p.strip() for p in pj.redes_sociais.split("|") if p.strip()]
            for part in parts:
                if ":" in part:
                    k, v = part.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k in ("linkedin", "instagram", "facebook") and v:
                        data["step_3"]["main"][k] = v

    def _preload_step4_bancario(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        bank = fornecedor.dados_bancarios.first()
        if not bank:
            return
        data["step_4"]["main"].update(
            {
                "banco": bank.banco,
                "agencia": bank.agencia,
                "conta": bank.conta,
                "tipo_chave_pix": bank.tipo_chave_pix,
                "chave_pix": bank.chave_pix,
            },
        )

    def _preload_step6_config(self, fornecedor: Fornecedor, data: dict[str, Any]) -> None:
        if getattr(fornecedor, "tipo_fornecimento", None):
            data["step_6"]["main"]["tipo_fornecimento"] = fornecedor.tipo_fornecimento
        data["step_6"]["main"]["prazo_pagamento_dias"] = getattr(fornecedor, "prazo_pagamento_dias", None)
        data["step_6"]["main"]["pedido_minimo"] = getattr(fornecedor, "pedido_minimo", None)
        data["step_6"]["main"]["prazo_medio_entrega_dias"] = getattr(fornecedor, "prazo_medio_entrega_dias", None)


# Funções auxiliares para URLs funcionais


def fornecedor_wizard_create(request: HttpRequest) -> HttpResponse:
    """Endpoint para iniciar criação de novo fornecedor via wizard."""
    return FornecedorWizardView.as_view()(request)


def fornecedor_wizard_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Endpoint para editar fornecedor existente via wizard."""
    return FornecedorWizardView.as_view()(request, pk=pk)


def fornecedor_wizard_goto_step(
    request: HttpRequest,
    step: int | str,
    pk: int | None = None,
) -> HttpResponse:
    """Permite pular para um step específico (validação de faixa)."""
    try:
        step_int = int(step)
    except (ValueError, TypeError):
        messages.error(request, _("Step inválido."))
        return redirect("fornecedores:fornecedores_list")
    if step_int in FORNECEDOR_WIZARD_STEPS:
        request.session["supplier_wizard_step"] = step_int
        request.session.modified = True
        if pk is not None:
            return redirect("fornecedores:fornecedor_wizard_edit", pk=pk)
        return redirect("fornecedores:fornecedor_wizard")
    messages.error(request, _("Step inválido."))
    return redirect("fornecedores:fornecedores_list")


def fornecedor_wizard_entry(request: HttpRequest) -> HttpResponse:
    """Redirecionar rota legada 'novo/' para entrada do wizard."""
    _ = request  # uso intencional para evitar aviso de argumento não utilizado
    return redirect("fornecedores:fornecedor_wizard")

import contextlib
import json
import logging
from typing import Any

from django.contrib import messages
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from cadastros_gerais.models import ItemAuxiliar
from core.utils import get_current_tenant
from core.wizard_base import get_wizard_config
from core.wizard_extensions import FornecedorWizardMixin
from core.wizard_forms import (
    TenantAddressWizardForm,
)
from core.wizard_views import TenantCreationWizardView

from .forms import FornecedorDocumentoVersaoCreateForm
from .models import (
    ContatoFornecedor,
    DadosBancariosFornecedor,
    EnderecoFornecedor,
    Fornecedor,
    FornecedorDocumento,
    FornecedorPF,
    FornecedorPJ,
)
from .wizard_forms import (
    FornecedorBankingWizardForm,
    FornecedorConfigWizardForm,
    FornecedorContactsExtendCoreForm,
    FornecedorDocumentsWizardForm,
    FornecedorPFIdentificationForm,
    FornecedorPJIdentificationForm,
    FornecedorReviewWizardForm,
)

logger = logging.getLogger(__name__)

FORNECEDOR_WIZARD_STEPS = {
    1: {
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
    2: {
        "name": "Endereços",
        "form_classes": {
            "main": TenantAddressWizardForm,
        },
        "template": "core/wizard/step_address.html",
        "icon": "fas fa-map-marker-alt",
        "description": "Endereço principal e adicionais",
    },
    3: {
        "name": "Contatos",
        "form_classes": {
            "main": FornecedorContactsExtendCoreForm,
        },
        "template": "fornecedores/wizard/step_contacts.html",
        "icon": "fas fa-phone",
        "description": "Contato principal e adicionais",
    },
    4: {
        "name": "Dados Bancários",
        "form_classes": {
            "main": FornecedorBankingWizardForm,
        },
        "template": "fornecedores/wizard/step_banking.html",
        "icon": "fas fa-university",
        "description": "Contas bancárias e PIX",
    },
    5: {
        "name": "Documentos",
        "form_classes": {
            "main": FornecedorDocumentsWizardForm,
        },
        "template": "fornecedores/wizard/step_documents.html",
        "icon": "fas fa-file-alt",
        "description": "Documentos do fornecedor (opcional)",
    },
    6: {
        "name": "Configurações",
        "form_classes": {
            "main": FornecedorConfigWizardForm,
        },
        "template": "fornecedores/wizard/step_config.html",
        "icon": "fas fa-gear",
        "description": "Preferências e tipo de fornecimento",
    },
    7: {
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
    # Lista padrão do módulo fornecedores
    success_url = reverse_lazy("fornecedores:fornecedores_list")

    @property
    def wizard_steps(self):
        # Preferir configuração central se existir
        try:
            cfg = get_wizard_config("fornecedor").get_wizard_steps()
            # Injetar templates específicos deste módulo
            mapped = {
                1: {
                    **cfg.get(1, {}),
                    "name": "Identificação",
                    "icon": "fas fa-truck",
                    "description": "Dados básicos do fornecedor",
                    "template": "core/wizard/step_identification.html",
                    "form_classes": {
                        "pj": FornecedorPJIdentificationForm,
                        "pf": FornecedorPFIdentificationForm,
                    },
                },
                2: {
                    **cfg.get(2, {}),
                    "name": "Endereços",
                    "icon": "fas fa-map-marker-alt",
                    "description": "Endereço principal e adicionais",
                    "template": "core/wizard/step_address.html",
                    "form_classes": {
                        "main": TenantAddressWizardForm,
                    },
                },
                3: {
                    **cfg.get(3, {}),
                    "name": "Contatos",
                    "icon": "fas fa-phone",
                    "description": "Contato principal e adicionais",
                    "template": "fornecedores/wizard/step_contacts.html",
                    "form_classes": {
                        "main": FornecedorContactsExtendCoreForm,
                    },
                },
                4: {
                    **cfg.get(4, {}),
                    "name": "Dados Bancários",
                    "icon": "fas fa-university",
                    "description": "Contas bancárias e PIX",
                    "template": "fornecedores/wizard/step_banking.html",
                    "form_classes": {
                        "main": FornecedorBankingWizardForm,
                    },
                },
                5: {
                    **cfg.get(5, {}),
                    "name": "Documentos",
                    "icon": "fas fa-file-alt",
                    "description": "Documentos do fornecedor (opcional)",
                    "template": "fornecedores/wizard/step_documents.html",
                    "form_classes": {
                        "main": FornecedorDocumentsWizardForm,
                    },
                },
                6: {
                    **cfg.get(6, {}),
                    "name": "Configurações",
                    "icon": "fas fa-gear",
                    "description": "Preferências e tipo de fornecimento",
                    "template": "fornecedores/wizard/step_config.html",
                    "form_classes": {
                        "main": FornecedorConfigWizardForm,
                    },
                },
                7: {
                    **cfg.get(7, {}),
                    "name": "Confirmação",
                    "icon": "fas fa-check-circle",
                    "description": "Revisão final",
                    "template": "fornecedores/wizard/step_confirmation.html",
                    "form_classes": {
                        "main": FornecedorReviewWizardForm,
                    },
                },
            }
            return mapped
        except Exception:
            return FORNECEDOR_WIZARD_STEPS

    def test_func(self) -> bool:
        # Permite superuser ou usuário com tenant
        if self.request.user.is_superuser:
            return True
        tenant = get_current_tenant(self.request)
        return tenant is not None

    def get_current_step(self) -> int:
        # Isolar chaves de sessão para não conflitar com outros wizards
        return self.request.session.get("supplier_wizard_step", 1)

    def set_current_step(self, step: int) -> None:
        self.request.session["supplier_wizard_step"] = step
        self.request.session.modified = True

    def get_wizard_data(self) -> dict[str, Any]:
        return self.request.session.get("supplier_wizard_data", {})

    def set_wizard_data(self, step: int, data: dict[str, Any]) -> None:
        wizard_data = self.get_wizard_data()
        wizard_data[f"step_{step}"] = data
        self.request.session["supplier_wizard_data"] = wizard_data
        self.request.session.modified = True

    def clear_wizard_data(self) -> None:
        self.request.session.pop("supplier_wizard_step", None)
        self.request.session.pop("supplier_wizard_data", None)
        self.request.session.modified = True

    def get_editing_tenant(self) -> Fornecedor | None:
        entity_pk = self.kwargs.get("pk")
        if not entity_pk:
            return None
        try:
            tenant = get_current_tenant(self.request)
            qs = Fornecedor.objects
            if not self.request.user.is_superuser and tenant:
                qs = qs.filter(tenant=tenant)
            return qs.get(pk=entity_pk)
        except Fornecedor.DoesNotExist:
            return None

    def create_forms_for_step(self, current_step, editing_entity, data_source="POST"):
        # Igual ao core, mas usando self.wizard_steps
        step_config = self.wizard_steps[current_step]
        form_classes = step_config["form_classes"]
        forms = {}
        for form_key, form_class in form_classes.items():
            # Step 5 (Documentos): quando em edição, usamos o form real de upload/versionamento
            if current_step == 5 and form_key == "main" and editing_entity:
                if data_source == "POST":
                    form = FornecedorDocumentoVersaoCreateForm(
                        self.request.POST, self.request.FILES, fornecedor=editing_entity, prefix=form_key
                    )
                else:
                    form = FornecedorDocumentoVersaoCreateForm(fornecedor=editing_entity, prefix=form_key)
            elif data_source == "POST":
                # Usar prefix para manter compatibilidade com templates (id_main-*, id_pj-*, etc.)
                if (
                    editing_entity
                    and hasattr(form_class, "_meta")
                    and getattr(form_class._meta, "model", None) in (Fornecedor, FornecedorPF, FornecedorPJ)
                ):
                    form = form_class(self.request.POST, self.request.FILES, prefix=form_key)
                else:
                    form = form_class(self.request.POST, self.request.FILES, prefix=form_key)
            else:
                saved_data = self.get_wizard_data().get(f"step_{current_step}", {})
                initial_data = saved_data.get(form_key, {})
                form = form_class(initial=initial_data, prefix=form_key)
            forms[form_key] = form
        return forms

    def process_step_data(self, forms):
        step_data = {}
        for form_key, form in forms.items():
            if form.is_valid():
                step_data[form_key] = form.cleaned_data.copy()
        return step_data

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        # Adaptar metadados do wizard (entity_name, verbose) via mixin
        with contextlib.suppress(Exception):
            self.adapt_wizard_for_entity()
        current_step = self.get_current_step()
        editing_entity = self.get_editing_tenant()
        # Se está editando e ainda não há dados na sessão do wizard de fornecedores, carregar
        if editing_entity and not self.get_wizard_data():
            self.load_fornecedor_data_to_wizard(editing_entity)
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        step_config = self.wizard_steps[current_step]
        forms = self.create_forms_for_step(current_step, editing_entity, data_source="GET")
        context = self.get_context_data(
            forms=forms, current_step=current_step, step_config=step_config, editing_tenant=editing_entity
        )
        return render(request, step_config["template"], context)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        current_step = self.get_current_step()
        editing_entity = self.get_editing_tenant()
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        step_config = self.wizard_steps[current_step]

        # Navegar para o passo anterior
        if "wizard_prev" in request.POST:
            if current_step > 1:
                self.set_current_step(current_step - 1)
            # Redirecionar mantendo o modo (edição ou criação)
            if editing_entity:
                return redirect("fornecedores:fornecedor_wizard_edit", pk=editing_entity.pk)
            return redirect("fornecedores:fornecedor_wizard")
        forms = self.create_forms_for_step(current_step, editing_entity, data_source="POST")
        is_finish_intent = "wizard_finish" in request.POST or current_step == len(self.wizard_steps)
        if is_finish_intent:
            # Para o Step 1, validar apenas o formulário do tipo selecionado (PF/PJ), como no core
            if current_step == 1:
                all_valid = self.validate_step_1_forms(forms)
            else:
                all_valid = all(form.is_valid() for form in forms.values() if form)
            if all_valid:
                # Step 5: se estiver em edição, salvar documento imediatamente (evitar armazenar arquivo na sessão)
                if current_step == 5 and editing_entity and "main" in forms:
                    try:
                        form_doc = forms["main"]
                        if getattr(form_doc, "cleaned_data", None) and form_doc.cleaned_data.get("arquivo"):
                            versao = form_doc.save(user=request.user)
                            messages.success(request, _("Documento enviado (v%(v)s).") % {"v": versao.versao})
                    except Exception as e:
                        messages.error(request, _("Falha ao enviar documento: ") + str(e))
                step_data = self.process_step_data(forms)
                self.set_wizard_data(current_step, step_data)
                return self.finish_wizard()
            else:
                context = self.get_context_data(
                    forms=forms, current_step=current_step, step_config=step_config, editing_tenant=editing_entity
                )
                # Necessário para alguns templates do CORE exibirem erros de nível de wizard
                context["wizard"] = self
                return render(request, step_config["template"], context)
        else:
            # Step 5: se em edição e form válido com arquivo, salvar imediatamente e NÃO guardar arquivo na sessão
            if current_step == 5 and editing_entity and "main" in forms:
                form_doc = forms["main"]
                if form_doc.is_valid() and form_doc.cleaned_data.get("arquivo"):
                    try:
                        versao = form_doc.save(user=request.user)
                        messages.success(request, _("Documento enviado (v%(v)s).") % {"v": versao.versao})
                    except Exception as e:
                        messages.error(request, _("Falha ao enviar documento: ") + str(e))
                # Não persistir dados do step 5 na sessão para evitar serialização de arquivo
            else:
                valid_step_data = self.process_step_data(forms)
                draft_step_data = self.collect_step_draft_data(forms, current_step)
                combined = dict(draft_step_data)
                combined.update(valid_step_data)
                self.set_wizard_data(current_step, combined)
            if current_step < len(self.wizard_steps):
                self.set_current_step(current_step + 1)
            return redirect(request.path)

    def finish_wizard(self):
        """Finaliza o wizard criando/atualizando Fornecedor, reutilizando dados do Step 1 do CORE."""
        wizard_data = self.get_wizard_data() or {}
        step1 = wizard_data.get("step_1", {}) or {}
        tenant = get_current_tenant(self.request)
        if not tenant:
            messages.error(self.request, _("Nenhuma empresa selecionada."))
            return redirect(self.success_url)

        # Detectar tipo de pessoa baseado nos dados do wizard (mesma lógica do CORE)
        tipo = self._detect_tipo_pessoa_from_wizard(wizard_data)
        if tipo not in ("PJ", "PF"):
            messages.error(self.request, _("Selecione Pessoa Física ou Jurídica e preencha os dados obrigatórios."))
            return redirect(self.success_url)

        pj = step1.get("pj", {}) or {}
        pf = step1.get("pf", {}) or {}

        try:
            from django.db import transaction

            with transaction.atomic():
                editing = self.get_editing_tenant()
                fornecedor = editing or Fornecedor(tenant=tenant)
                fornecedor.tipo_pessoa = tipo
                fornecedor.tenant = tenant
                fornecedor.save()

                if tipo == "PF":
                    pf_obj = getattr(fornecedor, "pessoafisica", None) or FornecedorPF(fornecedor=fornecedor)
                    # Mapear campos do CORE -> FornecedorPF
                    mapping = {
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
                    for src, dst in mapping.items():
                        if src in pf and hasattr(pf_obj, dst):
                            setattr(pf_obj, dst, pf.get(src))
                    pf_obj.save()
                else:
                    pj_obj = getattr(fornecedor, "pessoajuridica", None) or FornecedorPJ(fornecedor=fornecedor)
                    # Mapear campos do CORE -> FornecedorPJ
                    mapping = {
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
                        # Campos como email/telefone do CORE não existem aqui
                    }
                    for src, dst in mapping.items():
                        if src in pj and hasattr(pj_obj, dst):
                            setattr(pj_obj, dst, pj.get(src))
                    pj_obj.save()

                # Processar demais steps (endereços, contatos, bancos)
                self._process_other_steps(fornecedor, wizard_data)

                # limpar sessão
                self.clear_wizard_data()
                messages.success(self.request, _("Fornecedor salvo com sucesso."))
                from django.urls import reverse

                return redirect(reverse("fornecedores:fornecedor_detail", kwargs={"pk": fornecedor.pk}))
        except Exception as e:
            logger.exception("Erro ao salvar fornecedor")
            messages.error(self.request, _("Erro ao salvar fornecedor: ") + str(e))
            return redirect(self.success_url)

    def _process_other_steps(self, fornecedor: Fornecedor, wizard_data: dict[str, Any]):
        # Endereços (campos conforme TenantAddressWizardForm do CORE)
        step2 = wizard_data.get("step_2", {}).get("main", {})
        if step2:
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
            # adicionais via JSON
            raw_add = (step2.get("additional_addresses_json") or "").strip()
            if raw_add:
                try:
                    parsed = json.loads(raw_add)
                    EnderecoFornecedor.objects.filter(fornecedor=fornecedor).exclude(pk=addr.pk).delete()
                    for it in parsed[:50]:
                        if not isinstance(it, dict):
                            continue
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
                except Exception:
                    pass
        # Contatos (campos conforme TenantContactsWizardForm do CORE)
        step3 = wizard_data.get("step_3", {}).get("main", {})
        if step3:
            # Contato principal
            nome_contato = step3.get("nome_contato_principal") or "-"
            email_contato = step3.get("email_contato_principal") or ""
            telefone_contato = step3.get("telefone_contato_principal") or ""
            cargo_contato = step3.get("cargo_contato_principal") or ""
            if nome_contato or email_contato or telefone_contato:
                ContatoFornecedor.objects.update_or_create(
                    fornecedor=fornecedor,
                    nome=nome_contato,
                    defaults={
                        "email": email_contato,
                        "telefone": telefone_contato,
                        "cargo": cargo_contato,
                    },
                )
            # Contatos adicionais do CORE são departamentais (comercial/financeiro)
            if step3.get("nome_responsavel_comercial"):
                ContatoFornecedor.objects.update_or_create(
                    fornecedor=fornecedor,
                    nome=step3.get("nome_responsavel_comercial")[:100],
                    defaults={
                        "email": (step3.get("email_comercial") or "")[:255],
                        "telefone": (step3.get("telefone_comercial") or "")[:20],
                        "cargo": (step3.get("cargo_responsavel_comercial") or "Comercial")[:100],
                    },
                )
            if step3.get("nome_responsavel_financeiro"):
                ContatoFornecedor.objects.update_or_create(
                    fornecedor=fornecedor,
                    nome=step3.get("nome_responsavel_financeiro")[:100],
                    defaults={
                        "email": (step3.get("email_financeiro") or "")[:255],
                        "telefone": (step3.get("telefone_financeiro") or "")[:20],
                        "cargo": (step3.get("cargo_responsavel_financeiro") or "Financeiro")[:100],
                    },
                )
            # Vendedores (dinâmico via JSON)
            raw_vendors = (step3.get("additional_vendors_json") or "").strip()
            if raw_vendors:
                try:
                    parsed = json.loads(raw_vendors)
                    # Substituir lista de vendedores
                    ContatoFornecedor.objects.filter(fornecedor=fornecedor, cargo__iexact="Vendedor").delete()
                    for it in parsed[:100]:
                        if not isinstance(it, dict):
                            continue
                        ContatoFornecedor.objects.create(
                            fornecedor=fornecedor,
                            nome=(it.get("nome") or "-")[:100],
                            email=(it.get("email") or "")[:255],
                            telefone=(it.get("telefone") or "")[:20],
                            cargo="Vendedor",
                        )
                except Exception:
                    pass
            # Funcionários (prestação de serviços) - dinâmico via JSON com cargo
            raw_emps = (step3.get("additional_employees_json") or "").strip()
            if raw_emps:
                try:
                    parsed = json.loads(raw_emps)
                    # Estratégia: limpar e repovoar apenas os que têm cargo específico marcado como funcionários
                    # Para não apagar contatos departamentais e vendedores, removemos apenas cargos que existam no conjunto atual de funcionários
                    # Como não temos marker de funcionários na base, adotar política de idempotência simples: apagar todos que NÃO sejam Comercial/Financeiro/Vendedor e recriar a partir do JSON
                    preserved = ["Vendedor", "Comercial", "Financeiro"]
                    ContatoFornecedor.objects.filter(fornecedor=fornecedor).exclude(cargo__in=preserved).delete()
                    for it in parsed[:200]:
                        if not isinstance(it, dict):
                            continue
                        nome = (it.get("nome") or "-")[:100]
                        email = (it.get("email") or "")[:255]
                        telefone = (it.get("telefone") or "")[:20]
                        cargo = (it.get("cargo") or "-")[:100]
                        ContatoFornecedor.objects.create(
                            fornecedor=fornecedor,
                            nome=nome,
                            email=email,
                            telefone=telefone,
                            cargo=cargo,
                        )
                except Exception:
                    pass
            # Website e redes sociais no PJ
            try:
                if fornecedor.tipo_pessoa == "PJ" and hasattr(fornecedor, "pessoajuridica"):
                    pj_obj = fornecedor.pessoajuridica
                    pj_obj.website = (step3.get("website") or "")[:255]
                    socials = []
                    for key in ("linkedin", "instagram", "facebook"):
                        val = (step3.get(key) or "").strip()
                        if val:
                            socials.append(f"{key}:{val}")
                    pj_obj.redes_sociais = " | ".join(socials)[:255] if socials else (pj_obj.redes_sociais or "")
                    pj_obj.save(update_fields=["website", "redes_sociais"])
            except Exception:
                pass
        # Bancários
        step4 = wizard_data.get("step_4", {}).get("main", {})
        if step4:
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
                try:
                    parsed = json.loads(raw_bank)
                    for it in parsed[:50]:
                        if not isinstance(it, dict):
                            continue
                        if it.get("banco") and it.get("agencia") and it.get("conta"):
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
                except Exception:
                    pass
        # Configurações (tipo de fornecimento)
        step6 = wizard_data.get("step_6", {}).get("main", {})
        if step6:
            try:
                tipo = step6.get("tipo_fornecimento") or None
                if tipo in dict(Fornecedor.TIPO_FORNECIMENTO_CHOICES):
                    fornecedor.tipo_fornecimento = tipo
                # Novos campos
                fornecedor.regioes_atendidas = (step6.get("regioes_atendidas") or "").strip() or None
                fornecedor.prazo_pagamento_dias = step6.get("prazo_pagamento_dias") or None
                fornecedor.pedido_minimo = step6.get("pedido_minimo") or None
                fornecedor.prazo_medio_entrega_dias = step6.get("prazo_medio_entrega_dias") or None
                fornecedor.save(
                    update_fields=[
                        "tipo_fornecimento",
                        "regioes_atendidas",
                        "prazo_pagamento_dias",
                        "pedido_minimo",
                        "prazo_medio_entrega_dias",
                    ]
                )
                # M2M linhas fornecidas
                linhas = step6.get("linhas_fornecidas")
                if isinstance(linhas, list):
                    with contextlib.suppress(Exception):
                        fornecedor.linhas_fornecidas.set(linhas)
            except Exception:
                pass

    def get_context_data(self, **kwargs):
        """Contexto do wizard de fornecedores, independente do core wizard."""
        context = super(TenantCreationWizardView, self).get_context_data(**kwargs)
        current_step = kwargs.get("current_step", self.get_current_step())
        step_config = kwargs.get("step_config", self.wizard_steps.get(current_step, {}))
        editing_entity = kwargs.get("editing_tenant", self.get_editing_tenant())

        forms_dict = kwargs.get("forms")
        if forms_dict:
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
        try:
            step1 = wizard_data.get("step_1", {})
            pf = step1.get("pf", {})
            pj = step1.get("pj", {})
            if tipo == "PJ":
                preview_name = pj.get("name") or pj.get("nome_fantasia") or pj.get("razao_social") or preview_name
            elif tipo == "PF":
                preview_name = pf.get("name") or pf.get("nome_completo") or preview_name
        except Exception:
            pass
        try:
            step3 = wizard_data.get("step_3", {}).get("main", {})
            email = step3.get("email_contato_principal")
        except Exception:
            pass
        try:
            step2 = wizard_data.get("step_2", {}).get("main", {})
            cidade = step2.get("cidade")
            uf = step2.get("uf")
        except Exception:
            pass

        context.update(
            {
                "wizard_title": f"Editar Fornecedor - {editing_entity}"
                if editing_entity
                else "Cadastro de Novo Fornecedor",
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
                "step_title": step_config.get("name", f"Passo {current_step}")
                if step_config
                else f"Passo {current_step}",
                "step_icon": (step_config.get("icon", "fas fa-truck") if step_config else "fas fa-truck").replace(
                    "fas fa-", ""
                ),
                "wizard_data": wizard_data,
                "preview_card_title": "Preview do Fornecedor",
                "preview_name": preview_name,
                "preview_subtext": "Complete os dados do fornecedor",
                "preview_type_text": "Pessoa Jurídica"
                if tipo == "PJ"
                else ("Pessoa Física" if tipo == "PF" else "Tipo não definido"),
                "preview_email": email or "E-mail não informado",
                "preview_location": (f"{cidade}/{uf}" if cidade and uf else "Endereço não informado"),
                "preview_primary_badge": "Empresa" if tipo == "PJ" else "Pessoa",
                "preview_secondary_badge": "Em edição" if editing_entity else "Em criação",
                # Parametrização de rotas para o template base
                "wizard_goto_step_name": "fornecedores:fornecedor_wizard_goto_step",
                "wizard_goto_step_edit_name": "fornecedores:fornecedor_wizard_goto_step_edit",
                "wizard_goto_step_url_name": "fornecedores:fornecedor_wizard_goto_step",
                "wizard_list_url_name": "fornecedores:fornecedores_list",
            }
        )

        # Contexto adicional para o Step 5 (Documentos): listar tipos e histórico quando em edição
        if current_step == 5 and editing_entity:
            try:
                tipos_qs = ItemAuxiliar.objects.filter(ativo=True)
                tipos_qs = tipos_qs.filter(
                    models.Q(alvo="fornecedor") | models.Q(targets__code="fornecedor")
                ).distinct()
                tipos_qs = tipos_qs.select_related("categoria").order_by("categoria__ordem", "ordem", "nome")
                categorias = {}
                for tipo in tipos_qs:
                    cat = tipo.categoria
                    categorias.setdefault(cat, []).append(tipo)
                historico_por_tipo = {}
                for tipo in tipos_qs:
                    doc = FornecedorDocumento.objects.filter(fornecedor=editing_entity, tipo=tipo).first()
                    historico_por_tipo[tipo.pk] = (
                        list(doc.versoes.order_by("-enviado_em", "-versao")[:5]) if doc else []
                    )
                context.update(
                    {
                        "categorias": categorias,
                        "historico_por_tipo": historico_por_tipo,
                        "fornecedor": editing_entity,
                    }
                )
            except Exception:
                pass
        return context

    def load_fornecedor_data_to_wizard(self, fornecedor: Fornecedor) -> None:
        """Carrega dados existentes do fornecedor na sessão para edição."""
        data = {
            "step_1": {},
            "step_2": {"main": {}},
            "step_3": {"main": {}},
            "step_4": {"main": {}},
            "step_5": {"main": {}},
            "step_6": {"main": {}},
            "step_7": {"main": {}},
        }
        # Step 1
        # Manter 'main.tipo_pessoa' para compatibilidade com detecção
        data["step_1"]["main"] = {
            "tipo_pessoa": getattr(fornecedor, "tipo_pessoa", "PJ"),
        }
        if fornecedor.tipo_pessoa == "PJ" and hasattr(fornecedor, "pessoajuridica"):
            pj = fornecedor.pessoajuridica
            data["step_1"]["pj"] = {
                "tipo_pessoa": "PJ",
                # Mapeia 'name' (CORE) para nome_fantasia
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
                # Mapeia 'name' (CORE) para nome_completo
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
        # Step 2 - endereço principal
        end = fornecedor.enderecos.first()
        if end:
            data["step_2"]["main"].update(
                {
                    "logradouro": end.logradouro,
                    "numero": end.numero,
                    "complemento": end.complemento,
                    "bairro": end.bairro,
                    "cidade": end.cidade,
                    "uf": end.estado,
                    "cep": end.cep,
                }
            )
        # Step 3 - contatos no formato do CORE + website/redes sociais
        cont = fornecedor.contatos.first()
        if cont:
            data["step_3"]["main"].update(
                {
                    "nome_contato_principal": cont.nome,
                    "email_contato_principal": cont.email,
                    "telefone_contato_principal": cont.telefone,
                    "cargo_contato_principal": cont.cargo,
                }
            )
        # Contatos departamentais
        cont_com = fornecedor.contatos.filter(cargo__icontains="Comercial").first()
        if cont_com:
            data["step_3"]["main"].update(
                {
                    "nome_responsavel_comercial": cont_com.nome,
                    "email_comercial": cont_com.email,
                    "telefone_comercial": cont_com.telefone,
                    "cargo_responsavel_comercial": cont_com.cargo,
                }
            )
        cont_fin = fornecedor.contatos.filter(cargo__icontains="Financeiro").first()
        if cont_fin:
            data["step_3"]["main"].update(
                {
                    "nome_responsavel_financeiro": cont_fin.nome,
                    "email_financeiro": cont_fin.email,
                    "telefone_financeiro": cont_fin.telefone,
                    "cargo_responsavel_financeiro": cont_fin.cargo,
                }
            )
        # Vendedores -> preencher JSON inicial
        try:
            vendors = fornecedor.contatos.filter(cargo__iexact="Vendedor").values("nome", "email", "telefone")
            if vendors:
                import json as _json

                data["step_3"]["main"]["additional_vendors_json"] = _json.dumps(list(vendors), ensure_ascii=False)
        except Exception:
            pass
        # Funcionários (prestação de serviços) -> preencher JSON inicial (todos cargos que não forem Comercial/Financeiro/Vendedor)
        try:
            preserved = ["Vendedor", "Comercial", "Financeiro"]
            emps = fornecedor.contatos.exclude(cargo__in=preserved).values("nome", "email", "telefone", "cargo")
            if emps:
                import json as _json

                data["step_3"]["main"]["additional_employees_json"] = _json.dumps(list(emps), ensure_ascii=False)
        except Exception:
            pass
        # Website e Redes do PJ
        if fornecedor.tipo_pessoa == "PJ" and hasattr(fornecedor, "pessoajuridica"):
            pj = fornecedor.pessoajuridica
            if getattr(pj, "website", None):
                data["step_3"]["main"]["website"] = pj.website
            if getattr(pj, "redes_sociais", None):
                try:
                    parts = [p.strip() for p in pj.redes_sociais.split("|") if p.strip()]
                    for part in parts:
                        if ":" in part:
                            k, v = part.split(":", 1)
                            k = k.strip().lower()
                            v = v.strip()
                            if k in ("linkedin", "instagram", "facebook") and v:
                                data["step_3"]["main"][k] = v
                except Exception:
                    pass
        # Step 4 - dados bancários (pega primeiro)
        bank = fornecedor.dados_bancarios.first()
        if bank:
            data["step_4"]["main"].update(
                {
                    "banco": bank.banco,
                    "agencia": bank.agencia,
                    "conta": bank.conta,
                    "tipo_chave_pix": bank.tipo_chave_pix,
                    "chave_pix": bank.chave_pix,
                }
            )
        # Step 6 - configurações
        if getattr(fornecedor, "tipo_fornecimento", None):
            data["step_6"]["main"]["tipo_fornecimento"] = fornecedor.tipo_fornecimento
        # Preload novos campos de configuração
        try:
            data["step_6"]["main"]["regioes_atendidas"] = getattr(fornecedor, "regioes_atendidas", None)
            data["step_6"]["main"]["prazo_pagamento_dias"] = getattr(fornecedor, "prazo_pagamento_dias", None)
            data["step_6"]["main"]["pedido_minimo"] = getattr(fornecedor, "pedido_minimo", None)
            data["step_6"]["main"]["prazo_medio_entrega_dias"] = getattr(fornecedor, "prazo_medio_entrega_dias", None)
            # M2M como lista de IDs
            data["step_6"]["main"]["linhas_fornecidas"] = (
                list(fornecedor.linhas_fornecidas.values_list("id", flat=True))
                if hasattr(fornecedor, "linhas_fornecidas")
                else []
            )
        except Exception:
            pass
        # Persistir sessão
        self.request.session["supplier_wizard_data"] = data
        self.request.session["supplier_wizard_step"] = 1
        self.request.session.modified = True


# Funções auxiliares para URLs funcionais


def fornecedor_wizard_create(request):
    return FornecedorWizardView.as_view()(request)


def fornecedor_wizard_edit(request, pk):
    return FornecedorWizardView.as_view()(request, pk=pk)


def fornecedor_wizard_goto_step(request, step, pk=None):
    """Permite navegar diretamente para um step específico no wizard de fornecedores."""
    try:
        step = int(step)
    except (ValueError, TypeError):
        messages.error(request, _("Step inválido."))
        return redirect("fornecedores:fornecedores_list")

    if step in FORNECEDOR_WIZARD_STEPS:
        request.session["supplier_wizard_step"] = step
        request.session.modified = True
        if pk:
            return redirect("fornecedores:fornecedor_wizard_edit", pk=pk)
        return redirect("fornecedores:fornecedor_wizard")
    else:
        messages.error(request, _("Step inválido."))
        return redirect("fornecedores:fornecedores_list")


def fornecedor_wizard_entry(request):
    """Redireciona a rota antiga 'novo/' para a rota canônica do wizard."""
    return redirect("fornecedores:fornecedor_wizard")

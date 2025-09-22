import logging
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from clientes.models import Cliente
from core.utils import get_current_tenant
from core.wizard_forms import TenantAddressWizardForm
from core.wizard_views import TenantCreationWizardView

from .models import DocumentoObra, Obra
from .wizard_forms import (
    ObraConfigurationWizardForm,
    ObraContactsWizardForm,
    ObraDocumentsWizardForm,
    ObraIdentificationWizardForm,
)

logger = logging.getLogger(__name__)

OBRA_WIZARD_STEPS = {
    1: {
        "name": "Dados Iniciais",
        "form_classes": {"main": ObraIdentificationWizardForm},
        "template": "obras/wizard/step_identification.html",
        "icon": "fas fa-hard-hat",
        "description": "Informações básicas da obra",
    },
    2: {
        "name": "Endereços",
        "form_classes": {"main": TenantAddressWizardForm},
        "template": "core/wizard/step_address.html",
        "icon": "fas fa-map-marker-alt",
        "description": "Endereço principal e adicionais",
    },
    3: {
        "name": "Contatos",
        "form_classes": {"main": ObraContactsWizardForm},
        "template": "obras/wizard/step_contacts.html",
        "icon": "fas fa-user-tie",
        "description": "Responsável e contatos principais",
    },
    4: {
        "name": "Documentos",
        "form_classes": {"main": ObraDocumentsWizardForm},
        "template": "obras/wizard/step_documents.html",
        "icon": "fas fa-file-alt",
        "description": "Envio de documentos (opcional)",
    },
    5: {
        "name": "Configurações",
        "form_classes": {"main": ObraConfigurationWizardForm},
        "template": "obras/wizard/step_configuration.html",
        "icon": "fas fa-cogs",
        "description": "Status, progresso e observações",
    },
}


class ObraWizardView(TenantCreationWizardView):
    success_url = reverse_lazy("obras:obras_list")

    @property
    def wizard_steps(self):
        return OBRA_WIZARD_STEPS

    # Isolar sessão para este wizard
    def get_current_step(self) -> int:
        return self.request.session.get("obra_wizard_step", 1)

    def set_current_step(self, step: int) -> None:
        self.request.session["obra_wizard_step"] = step
        self.request.session.modified = True

    def get_wizard_data(self) -> dict[str, Any]:
        return self.request.session.get("obra_wizard_data", {})

    def set_wizard_data(self, step: int, data: dict[str, Any]) -> None:
        wizard_data = self.get_wizard_data()
        wizard_data[f"step_{step}"] = data
        self.request.session["obra_wizard_data"] = wizard_data
        self.request.session.modified = True

    def clear_wizard_data(self) -> None:
        for key in ("obra_wizard_step", "obra_wizard_data"):
            self.request.session.pop(key, None)
        self.request.session.modified = True

    # Objeto em edição (quando houver)
    def get_editing_tenant(self) -> Obra | None:
        pk = self.kwargs.get("pk")
        if not pk:
            return None
        try:
            tenant = get_current_tenant(self.request)
            qs = Obra.objects
            if not self.request.user.is_superuser and hasattr(Obra, "tenant") and tenant:
                qs = qs.filter(tenant=tenant)
            return qs.get(pk=pk)
        except Obra.DoesNotExist:
            return None

    # Construção de formulários por step
    def create_forms_for_step(self, current_step, editing_entity, data_source="POST"):
        step_config = self.wizard_steps[current_step]
        form_classes = step_config["form_classes"]
        forms = {}
        for form_key, form_class in form_classes.items():
            if data_source == "POST":
                kwargs = {"data": self.request.POST, "files": self.request.FILES, "prefix": form_key}
                # Passar request quando suportado (identificação usa para filtrar clientes)
                try:
                    forms[form_key] = form_class(**kwargs, request=self.request)
                except TypeError:
                    forms[form_key] = form_class(**kwargs)
            else:
                saved = self.get_wizard_data().get(f"step_{current_step}", {})
                initial = saved.get(form_key, {})
                try:
                    forms[form_key] = form_class(initial=initial, prefix=form_key, request=self.request)
                except TypeError:
                    forms[form_key] = form_class(initial=initial, prefix=form_key)
        return forms

    def _serialize_value(self, v):
        """Converte valores do cleaned_data para formatos serializáveis em JSON (sessão)."""
        try:
            # Arquivos já filtrados antes
            if getattr(v, "read", None) is not None:
                return None
            # Model instance
            if hasattr(v, "_meta") and hasattr(v, "pk"):
                return v.pk
            # Date/Datetime
            from datetime import date, datetime

            if isinstance(v, (date, datetime)):
                return v.isoformat()
            # Decimal
            from decimal import Decimal

            if isinstance(v, Decimal):
                return str(v)
            # List/Tuple (ex.: múltiplos arquivos, escolhas múltiplas)
            if isinstance(v, (list, tuple)):
                return [self._serialize_value(i) for i in v]
            return v
        except Exception:
            return str(v)

    def process_step_data(self, forms):
        step_data = {}
        for key, form in forms.items():
            if form.is_valid():
                cleaned = {}
                for k, v in form.cleaned_data.items():
                    if getattr(v, "read", None) is not None:
                        continue  # ignora arquivos na sessão
                    cleaned[k] = self._serialize_value(v)
                step_data[key] = cleaned
        return step_data

    def get_context_data(self, **kwargs):
        """Contexto específico para o wizard de Obras (títulos, navegação e preview)."""
        context = {}
        current_step = kwargs.get("current_step") or self.get_current_step()
        editing = kwargs.get("editing_tenant") or self.get_editing_tenant()
        step_config = kwargs.get("step_config") or self.wizard_steps.get(current_step, {})

        # Forms
        forms_dict = kwargs.get("forms")
        if forms_dict:
            context["forms"] = forms_dict
            if len(forms_dict) == 1 and "main" in forms_dict:
                context["form"] = forms_dict["main"]

        # Dados salvos na sessão (organizado)
        raw_data = self.get_wizard_data() or {}
        wizard_data = {}
        for step_key, step_val in raw_data.items():
            if isinstance(step_val, dict) and any(k in step_val for k in ("main", "pj", "pf")):
                wizard_data[step_key] = step_val
            else:
                wizard_data[step_key] = {"main": step_val if isinstance(step_val, dict) else {}}

        # Prévia (Preview) da Obra
        step1 = wizard_data.get("step_1", {}).get("main", {})
        step2 = wizard_data.get("step_2", {}).get("main", {})
        nome = step1.get("nome") or (getattr(editing, "nome", None)) or "Nova Obra"
        tipo_code = step1.get("tipo_obra") or (getattr(editing, "tipo_obra", None))
        tipo_map = dict(Obra.TIPO_OBRA_CHOICES)
        tipo_txt = tipo_map.get(tipo_code, "Tipo não definido") if tipo_code else "Tipo não definido"
        cliente_id = step1.get("cliente") or (getattr(editing, "cliente_id", None))
        cliente_nome = None
        if cliente_id:
            try:
                cliente_nome = Cliente.objects.filter(pk=cliente_id).values_list("nome", flat=True).first()
            except Exception:
                cliente_nome = None
        endereco_preview = None
        if step2:
            logradouro = step2.get("logradouro") or ""
            numero = step2.get("numero") or ""
            comp = step2.get("complemento") or ""
            cidade = step2.get("cidade") or ""
            uf = step2.get("uf") or ""
            endereco_preview = logradouro
            if numero:
                endereco_preview = f"{endereco_preview}, {numero}" if endereco_preview else numero
            if comp:
                endereco_preview = f"{endereco_preview} - {comp}" if endereco_preview else comp
            loc = " / ".join([p for p in [cidade, uf] if p])
            if loc:
                endereco_preview = f"{endereco_preview} - {loc}" if endereco_preview else loc
        elif editing:
            endereco_preview = getattr(editing, "endereco", None)
            loc = " / ".join([p for p in [getattr(editing, "cidade", ""), getattr(editing, "estado", "")] if p])
            if loc:
                endereco_preview = f"{endereco_preview} - {loc}" if endereco_preview else loc

        context.update(
            {
                # Títulos e navegação
                "wizard_title": f"Editar Obra - {editing.nome}" if editing else "Cadastro de Nova Obra",
                "current_step": current_step,
                "total_steps": len(self.wizard_steps),
                "step_config": step_config,
                "steps_list": self.wizard_steps,
                "progress_percentage": (current_step / max(1, len(self.wizard_steps))) * 100,
                "can_go_prev": current_step > 1,
                "can_go_next": current_step < len(self.wizard_steps),
                "is_last_step": current_step == len(self.wizard_steps),
                "is_editing": editing is not None,
                "editing_tenant": editing,
                "step_title": step_config.get("name", f"Passo {current_step}")
                if step_config
                else f"Passo {current_step}",
                "step_icon": (step_config.get("icon", "fas fa-hard-hat") if step_config else "fas fa-hard-hat").replace(
                    "fas fa-", ""
                ),
                # Rotas de navegação específicas do módulo Obras
                "wizard_goto_step_name": "obras:obra_wizard_goto_step",
                "wizard_goto_step_edit_name": "obras:obra_wizard_goto_step_edit",
                "wizard_list_url_name": "obras:obras_list",
                # Dados brutos do wizard
                "wizard_data": wizard_data,
                # Preview personalizado
                "preview_card_title": "Preview da Obra",
                "preview_name": nome,
                "preview_subtext": "Complete os dados da obra",
                "preview_type_text": tipo_txt,
                "preview_email": f"Cliente: {cliente_nome}" if cliente_nome else "Cliente não informado",
                "preview_location": endereco_preview or "Endereço não informado",
                "preview_primary_badge": "Obra",
                "preview_secondary_badge": "Edição" if editing else "Cadastro",
            }
        )

        return context

    # GET/POST (igual aos demais wizards)
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        current_step = self.get_current_step()
        editing = self.get_editing_tenant()
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        step_config = self.wizard_steps[current_step]
        forms = self.create_forms_for_step(current_step, editing, data_source="GET")
        ctx = self.get_context_data(
            forms=forms,
            current_step=current_step,
            step_config=step_config,
            editing_tenant=editing,
        )
        return render(request, step_config["template"], ctx)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        current_step = self.get_current_step()
        editing = self.get_editing_tenant()
        if current_step not in self.wizard_steps:
            messages.error(request, _("Step inválido."))
            return redirect(self.success_url)
        step_config = self.wizard_steps[current_step]

        if "wizard_prev" in request.POST:
            if current_step > 1:
                self.set_current_step(current_step - 1)
            if editing:
                return redirect("obras:obra_wizard_edit", pk=editing.pk)
            return redirect("obras:obra_wizard")

        forms = self.create_forms_for_step(current_step, editing, data_source="POST")
        is_finish = "wizard_finish" in request.POST or current_step == len(self.wizard_steps)

        if is_finish:
            all_valid = all(f.is_valid() for f in forms.values())
            if all_valid:
                self.set_wizard_data(current_step, self.process_step_data(forms))
                return self.finish_wizard()
            ctx = self.get_context_data(
                forms=forms, current_step=current_step, step_config=step_config, editing_tenant=editing
            )
            ctx["wizard"] = self
            return render(request, step_config["template"], ctx)
        else:
            valid_step_data = self.process_step_data(forms)
            self.set_wizard_data(current_step, valid_step_data)
            if current_step < len(self.wizard_steps):
                self.set_current_step(current_step + 1)
            return redirect(request.path)

    def finish_wizard(self):
        data = self.get_wizard_data() or {}
        step1 = data.get("step_1", {}).get("main", {})
        step2 = data.get("step_2", {}).get("main", {})
        step3 = data.get("step_3", {}).get("main", {})
        step5 = data.get("step_5", {}).get("main", {})

        try:
            from django.db import transaction

            with transaction.atomic():
                editing = self.get_editing_tenant()
                obra = editing or Obra()
                # Step 1
                for field in ("nome", "tipo_obra", "cno", "data_inicio", "data_previsao_termino", "valor_contrato"):
                    if field in step1:
                        setattr(obra, field, step1.get(field))
                # Cliente pode vir como PK serializada
                if "cliente" in step1 and step1.get("cliente"):
                    try:
                        obra.cliente = Cliente.objects.get(pk=step1.get("cliente"))
                    except Exception:
                        obra.cliente = None
                # Step 2 -> mapeia para campos simples do modelo Obra
                obra.cep = step2.get("cep") or ""
                obra.endereco = step2.get("logradouro") or ""
                numero = step2.get("numero") or ""
                comp = step2.get("complemento") or ""
                if numero or comp:
                    obra.endereco = f"{obra.endereco}, {numero}{(' - ' + comp) if comp else ''}"
                obra.cidade = step2.get("cidade") or ""
                obra.estado = step2.get("uf") or ""
                # País é ignorado por enquanto
                obra.observacoes = step5.get("observacoes") or ""
                # Step 5
                if "status" in step5:
                    obra.status = step5.get("status")
                if "progresso" in step5:
                    obra.progresso = step5.get("progresso") or 0
                if "valor_total" in step5:
                    obra.valor_total = step5.get("valor_total") or obra.valor_contrato
                if "data_termino" in step5:
                    obra.data_termino = step5.get("data_termino") or None
                # Adicionar resumo dos contatos nas observações
                contato_parts = []
                if any(step3.get(k) for k in ("responsavel_nome", "responsavel_email", "responsavel_telefone")):
                    contato_parts.append("Contato: ")
                    if step3.get("responsavel_nome"):
                        contato_parts.append(step3.get("responsavel_nome"))
                    if step3.get("responsavel_cargo"):
                        contato_parts.append(f"({step3.get('responsavel_cargo')})")
                    if step3.get("responsavel_email"):
                        contato_parts.append(f" - {step3.get('responsavel_email')}")
                    if step3.get("responsavel_telefone"):
                        contato_parts.append(f" - {step3.get('responsavel_telefone')}")
                extra = " ".join(contato_parts).strip()
                if extra:
                    obra.observacoes = (obra.observacoes or "") + "\n" + extra

                obra.save()

                # Step 4: documentos enviados devem ser processados a partir do request.FILES
                files = self.request.FILES.getlist("main-documentos")
                for f in files[:10]:
                    DocumentoObra.objects.create(obra=obra, descricao=f.name, arquivo=f)

                # Limpar sessão e redirecionar
                self.clear_wizard_data()
                messages.success(self.request, _("Obra salva com sucesso."))
                return redirect(reverse("obras:obra_detail", kwargs={"pk": obra.pk}))
        except Exception as e:
            logger.exception("Erro ao salvar obra via wizard")
            messages.error(self.request, _("Erro ao salvar obra: ") + str(e))
            return redirect(self.success_url)


# Rotas utilitárias (goto step)


def obra_wizard_create(request):
    return ObraWizardView.as_view()(request)


def obra_wizard_edit(request, pk):
    return ObraWizardView.as_view()(request, pk=pk)


def obra_wizard_goto_step(request, step, pk=None):
    try:
        step = int(step)
    except (TypeError, ValueError):
        messages.error(request, _("Step inválido."))
        return redirect("obras:obras_list")
    if step in OBRA_WIZARD_STEPS:
        request.session["obra_wizard_step"] = step
        request.session.modified = True
        if pk:
            return redirect("obras:obra_wizard_edit", pk=pk)
        return redirect("obras:obra_wizard")
    messages.error(request, _("Step inválido."))
    return redirect("obras:obras_list")

"""funcionarios/wizard_views.py
Wizard de cadastro/edição de Funcionários baseado em sessões.
"""

import contextlib

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from core.mixins import TenantRequiredMixin
from core.utils import get_current_tenant

from .models import Funcionario, FuncionarioHorario, SalarioHistorico
from .wizard_forms import (
    FuncionarioAddressForm,
    FuncionarioConfirmForm,
    FuncionarioContatoEmergenciaForm,
    FuncionarioContratoForm,
    FuncionarioIdentificationForm,
)

FUNCIONARIO_WIZARD_STEPS = {
    1: {
        "name": "Identificação",
        "form_classes": {"main": FuncionarioIdentificationForm},
        "template": "funcionarios/wizard/step_identification.html",
        "icon": "fas fa-id-card",
    },
    2: {
        "name": "Endereço",
        "form_classes": {"main": FuncionarioAddressForm},
        "template": "funcionarios/wizard/step_address.html",
        "icon": "fas fa-map-marker-alt",
    },
    3: {
        "name": "Contatos",
        "form_classes": {"main": FuncionarioContatoEmergenciaForm},
        "template": "funcionarios/wizard/step_contatos.html",
        "icon": "fas fa-phone",
    },
    4: {
        "name": "Contrato & Salário",
        "form_classes": {"main": FuncionarioContratoForm},
        "template": "funcionarios/wizard/step_contrato.html",
        "icon": "fas fa-briefcase",
    },
    5: {
        "name": "Confirmação",
        "form_classes": {"main": FuncionarioConfirmForm},
        "template": "funcionarios/wizard/step_confirmation.html",
        "icon": "fas fa-check-circle",
    },
}


class FuncionarioWizardView(LoginRequiredMixin, TenantRequiredMixin, TemplateView):
    template_name = "funcionarios/wizard/step_identification.html"
    success_url = reverse_lazy("funcionarios:funcionario_list")
    session_step_key = "funcionario_wizard_step"
    session_data_key = "funcionario_wizard_data"

    def get_steps(self):
        return FUNCIONARIO_WIZARD_STEPS

    def get_current_step(self):
        return self.request.session.get(self.session_step_key, 1)

    def set_current_step(self, step: int):
        self.request.session[self.session_step_key] = step
        self.request.session.modified = True

    def get_wizard_data(self):
        return self.request.session.get(self.session_data_key, {})

    def set_wizard_data(self, step: int, data: dict):
        all_data = self.get_wizard_data()
        all_data[f"step_{step}"] = data
        self.request.session[self.session_data_key] = all_data
        self.request.session.modified = True

    def clear_wizard(self):
        self.request.session.pop(self.session_step_key, None)
        self.request.session.pop(self.session_data_key, None)
        self.request.session.modified = True

    def get_editing_instance(self):
        pk = self.kwargs.get("pk")
        if not pk:
            return None
        try:
            tenant = get_current_tenant(self.request)
            qs = Funcionario.objects
            if tenant and not self.request.user.is_superuser:
                qs = qs.filter(tenant=tenant)
            return qs.get(pk=pk)
        except Funcionario.DoesNotExist:
            return None

    def preload_instance_data(self, instance: Funcionario):
        """Carrega dados do funcionário existente na sessão para modo edição."""
        data = {}
        # Step 1 identificação (+ dependentes)
        data["step_1"] = {
            "main": {
                "nome_completo": instance.nome_completo,
                "cpf": instance.cpf,
                "rg": instance.rg,
                "data_nascimento": instance.data_nascimento,
                "sexo": instance.sexo,
                "estado_civil": instance.estado_civil,
                "nacionalidade": instance.nacionalidade,
                "escolaridade": instance.escolaridade,
                "pis": instance.pis,
                "ctps": instance.ctps,
                "titulo_eleitor": instance.titulo_eleitor,
                "reservista": instance.reservista,
            },
            "dependentes": {"dependentes_json": self.serialize_dependentes(instance)},
        }
        # Step 2 endereço
        data["step_2"] = {
            "main": {
                "endereco_cep": instance.endereco_cep,
                "endereco_logradouro": instance.endereco_logradouro,
                "endereco_numero": instance.endereco_numero,
                "endereco_complemento": instance.endereco_complemento,
                "endereco_bairro": instance.endereco_bairro,
                "endereco_cidade": instance.endereco_cidade,
                "endereco_uf": instance.endereco_uf,
                "endereco_pais": getattr(instance, "endereco_pais", "Brasil"),
            }
        }
        # Step 3 contatos/emergência
        data["step_3"] = {
            "main": {
                "telefone_pessoal": instance.telefone_pessoal,
                "telefone_secundario": getattr(instance, "telefone_secundario", None),
                "email_pessoal": instance.email_pessoal,
                "telefone_emergencia": instance.telefone_emergencia,
                "contato_emergencia": instance.contato_emergencia,
                "observacoes": instance.observacoes,
            }
        }
        # Step 4 contrato & salário (fundidos)
        data["step_4"] = {
            "main": {
                "data_admissao": instance.data_admissao,
                "tipo_contrato": instance.tipo_contrato,
                "cargo": instance.cargo,
                "departamento": instance.departamento_id,
                "jornada_trabalho_horas": instance.jornada_trabalho_horas,
                "horario_entrada": getattr(instance, "horario_entrada", None),
                "horario_saida": getattr(instance, "horario_saida", None),
                "intervalo_inicio": getattr(instance, "intervalo_inicio", None),
                "intervalo_fim": getattr(instance, "intervalo_fim", None),
                "salario_base": instance.salario_base,
                "cnpj_prestador": getattr(instance, "cnpj_prestador", None),
                "pj_categoria": getattr(instance, "pj_categoria", None),
                "banco": instance.banco,
                "agencia": instance.agencia,
                "conta": instance.conta,
                "tipo_conta": instance.tipo_conta,
                "ativo": instance.ativo,
                "horarios_json": self.serialize_horarios(instance),
            }
        }
        # Step 5 confirmação
        data["step_5"] = {"main": {}}
        self.request.session[self.session_data_key] = data
        self.request.session[self.session_step_key] = 1
        self.request.session.modified = True

    def serialize_dependentes(self, funcionario: Funcionario):
        import json

        items = []
        for d in funcionario.dependentes.all():
            items.append(
                {
                    "nome": getattr(d, "nome_completo", ""),
                    "cpf": d.cpf,
                    "data_nascimento": d.data_nascimento.strftime("%Y-%m-%d") if d.data_nascimento else None,
                    "tipo": d.tipo_dependente,
                    "ir": d.dependente_ir,
                    "salario_familia": d.dependente_salario_familia,
                }
            )
        return json.dumps(items, ensure_ascii=False)

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        step = self.get_current_step()
        steps = self.get_steps()
        if step not in steps:
            step = 1
            self.set_current_step(step)
        editing = self.get_editing_instance()
        if editing and not self.get_wizard_data():
            self.preload_instance_data(editing)
        context = self.build_context(step, editing_instance=editing)
        return render(request, steps[step]["template"], context)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        action = (
            request.POST.get("wizard_action") or request.POST.get("wizard_prev") or request.POST.get("wizard_save_step")
        )
        step = self.get_current_step()
        steps = self.get_steps()
        editing = self.get_editing_instance()
        context = self.build_context(step, bind=True, editing_instance=editing)
        forms = context["forms"]

        # Validação apenas se não for navegação para trás
        if action not in ("wizard_prev", "back"):
            valid = all(f.is_valid() for f in forms.values())
            if not valid and action not in ("wizard_prev", "back"):
                return render(request, steps[step]["template"], context)

        # Voltar
        if action in ("wizard_prev", "back"):
            prev_step = max(1, step - 1)
            self.set_current_step(prev_step)
            return redirect(self.get_step_url(prev_step, pk=editing.pk if editing else None))

        # Salvar passo isoladamente em modo edição
        if action == "save":
            self.set_wizard_data(step, {k: f.cleaned_data for k, f in forms.items() if f.is_valid()})
            if editing:
                self.persist_editing_instance(editing)
                messages.success(request, _("Passo salvo."))
            return redirect(self.get_step_url(step, pk=editing.pk if editing else None))

        # Próximo
        if action == "next":
            self.set_wizard_data(step, {k: f.cleaned_data for k, f in forms.items() if f.is_valid()})
            next_step = min(len(steps), step + 1)
            self.set_current_step(next_step)
            return redirect(self.get_step_url(next_step, pk=editing.pk if editing else None))

        # Finalizar
        if action == "finish" and step == max(steps.keys()):
            self.set_wizard_data(step, {k: f.cleaned_data for k, f in forms.items() if f.is_valid()})
            if editing:
                return self.finish_wizard(editing_instance=editing)
            return self.finish_wizard()

        messages.error(request, _("Ação inválida."))
        return redirect(self.get_step_url(step, pk=editing.pk if editing else None))

    def build_context(self, step: int, bind: bool = False, editing_instance: Funcionario = None):
        steps = self.get_steps()
        step_conf = steps[step]
        wizard_data = self.get_wizard_data()
        stored = wizard_data.get(f"step_{step}", {})
        tenant = get_current_tenant(self.request)

        forms = {}
        for key, form_cls in step_conf["form_classes"].items():
            kwargs = {}
            if form_cls in (FuncionarioContratoForm,):
                kwargs["tenant"] = tenant
            if bind and self.request.method == "POST":
                forms[key] = form_cls(self.request.POST, **kwargs)
            else:
                forms[key] = form_cls(initial=stored.get(key), **kwargs)

        total_steps = len(steps)
        preview_name = (
            editing_instance.nome_completo if editing_instance else stored.get("main", {}).get("nome_completo")
        ) or "Novo Funcionário"
        # E-mail para preview: pega do step atual ou do step de contatos (agora 3)
        preview_email = stored.get("main", {}).get("email_pessoal") if stored else None
        if not preview_email:
            preview_email = wizard_data.get("step_3", {}).get("main", {}).get("email_pessoal")
        endereco_preview = None
        try:
            addr = wizard_data.get("step_2", {}).get("main", {})
            if addr.get("endereco_cidade") and addr.get("endereco_uf"):
                endereco_preview = f"{addr.get('endereco_cidade')}/{addr.get('endereco_uf')}"
        except Exception:
            pass
        return {
            "current_step": step,
            "steps_meta": steps,
            "steps_list": steps,
            "forms": forms,
            "page_title": f"Funcionário - Passo {step}: {step_conf['name']}",
            "wizard_total_steps": total_steps,
            "wizard_goto_step_url_name": "funcionarios:funcionario_wizard_goto_step_edit"
            if editing_instance
            else "funcionarios:funcionario_wizard_goto_step",
            "is_last_step": step == total_steps,
            "progress_percentage": int((step / total_steps) * 100),
            # Variáveis esperadas pelo template base para remover aparência de empresa
            "wizard_title": f"Editar Funcionário - {editing_instance.nome_completo}"
            if editing_instance
            else "Cadastro de Novo Funcionário",
            "wizard_subtitle": "Preencha os dados do colaborador",
            "step_title": step_conf.get("name"),
            "step_icon": step_conf.get("icon", "fa-user").replace("fas fa-", ""),
            "preview_icon": "user",
            "preview_card_title": "Preview do Funcionário",
            "preview_name": preview_name,
            "preview_subtext": "Complete os dados do funcionário",
            "preview_type_text": "Colaborador",
            "preview_email": preview_email or "E-mail não informado",
            "preview_location": endereco_preview or "Endereço não informado",
            "preview_primary_badge": "Funcionário",
            "preview_secondary_badge": "Em edição" if editing_instance else "Em criação",
            "is_editing": editing_instance is not None,
        }

    def get_step_url(self, step: int, pk: int = None) -> str:
        if pk:
            return reverse("funcionarios:funcionario_wizard_goto_step_edit", kwargs={"step": step, "pk": pk})
        return reverse("funcionarios:funcionario_wizard_goto_step", kwargs={"step": step})

    def persist_editing_instance(self, instance: Funcionario):
        """Aplica dados da sessão ao objeto existente sem criar novo."""
        wizard_data = self.get_wizard_data()
        payload = {}
        for s_val in wizard_data.values():
            if isinstance(s_val, dict):
                for form_data in s_val.values():
                    if isinstance(form_data, dict):
                        payload.update(form_data)
        field_names = [f.name for f in Funcionario._meta.fields]
        changed = []
        for k, v in payload.items():
            if k in field_names and getattr(instance, k) != v:
                setattr(instance, k, v)
                changed.append(k)
        if changed:
            instance.save(update_fields=changed)
            if "salario_base" in changed and instance.salario_base:
                # Registrar histórico
                with contextlib.suppress(Exception):
                    SalarioHistorico.objects.create(
                        tenant=instance.tenant,
                        funcionario=instance,
                        data_vigencia=payload.get("data_admissao") or instance.data_admissao,
                        valor_salario=instance.salario_base,
                        motivo_alteracao="Alteração via wizard",
                    )
        # Horários detalhados
        horarios_json = payload.get("horarios_json")
        if horarios_json is not None:
            self.apply_horarios_from_json(instance, horarios_json)
        # Dependentes
        dependentes_json = payload.get("dependentes_json")
        if dependentes_json is not None:
            import json

            from .models import Dependente

            try:
                deps = json.loads(dependentes_json) if dependentes_json else []
            except Exception:
                deps = []
            # Estratégia simples: apagar e recriar
            instance.dependentes.all().delete()
            if isinstance(deps, list) and deps:
                dep_objs = []
                for d in deps:
                    try:
                        nome = d.get("nome") or d.get("nome_completo")
                        if not nome:
                            continue
                        dep_objs.append(
                            Dependente(
                                tenant=instance.tenant,
                                funcionario=instance,
                                nome_completo=nome,
                                cpf=d.get("cpf") or None,
                                data_nascimento=d.get("data_nascimento") or d.get("nascimento"),
                                tipo_dependente=d.get("tipo") or d.get("tipo_dependente") or "OUTRO",
                                dependente_ir=bool(d.get("ir", True)),
                                dependente_salario_familia=bool(d.get("salario_familia", True)),
                            )
                        )
                    except Exception:
                        continue
                # Converter datas
                from datetime import date, datetime

                for o in dep_objs:
                    if isinstance(o.data_nascimento, str) and o.data_nascimento:
                        try:
                            o.data_nascimento = datetime.strptime(o.data_nascimento, "%Y-%m-%d").date()
                        except Exception:
                            o.data_nascimento = date.today()
                if dep_objs:
                    Dependente.objects.bulk_create(dep_objs)
        return instance

    def serialize_horarios(self, funcionario: Funcionario):
        import json

        items = []
        for h in funcionario.horarios.filter(ativo=True).order_by("dia_semana", "ordem"):
            items.append(
                {
                    "id": h.id,
                    "dia_semana": h.dia_semana,
                    "ordem": h.ordem,
                    "entrada": h.entrada.strftime("%H:%M") if h.entrada else "",
                    "saida": h.saida.strftime("%H:%M") if h.saida else "",
                    "intervalo_inicio": h.intervalo_inicio.strftime("%H:%M") if h.intervalo_inicio else "",
                    "intervalo_fim": h.intervalo_fim.strftime("%H:%M") if h.intervalo_fim else "",
                    "horas_previstas": float(h.horas_previstas) if h.horas_previstas is not None else None,
                }
            )
        return json.dumps(items, ensure_ascii=False)

    def apply_horarios_from_json(self, funcionario: Funcionario, horarios_json: str):
        import json

        try:
            data = json.loads(horarios_json) if horarios_json else []
        except Exception:
            data = []
        # Estratégia simples: apaga existentes e recria (pouco volume esperado)
        funcionario.horarios.all().delete()
        objs = []
        for item in data:
            try:
                objs.append(
                    FuncionarioHorario(
                        funcionario=funcionario,
                        dia_semana=int(item.get("dia_semana")),
                        ordem=int(item.get("ordem", 1)),
                        entrada=item.get("entrada") or None,
                        saida=item.get("saida") or None,
                        intervalo_inicio=item.get("intervalo_inicio") or None,
                        intervalo_fim=item.get("intervalo_fim") or None,
                    )
                )
            except Exception:
                continue
        if objs:
            # Necessário converter strings HH:MM para time objects
            from datetime import datetime

            fmt = "%H:%M"
            for o in objs:
                for attr in ["entrada", "saida", "intervalo_inicio", "intervalo_fim"]:
                    val = getattr(o, attr)
                    if isinstance(val, str) and val:
                        try:
                            setattr(o, attr, datetime.strptime(val, fmt).time())
                        except Exception:
                            setattr(o, attr, None)
            FuncionarioHorario.objects.bulk_create(objs)

    def finish_wizard(self, editing_instance: Funcionario = None):
        data = self.get_wizard_data()
        if not data.get("step_1"):
            messages.error(self.request, _("Dados insuficientes."))
            return redirect(self.get_step_url(1))
        tenant = get_current_tenant(self.request)
        if not tenant:
            messages.error(self.request, _("Tenant não definido."))
            return redirect(self.get_step_url(1))

        payload = {}
        for _s_key, s_val in data.items():
            if isinstance(s_val, dict):
                for _form_key, form_data in s_val.items():
                    if isinstance(form_data, dict):
                        payload.update(form_data)

        # Limpeza/padronização de JSON de endereços adicionais (se existir)
        add_json = payload.get("additional_addresses_json")
        if add_json:
            import json

            try:
                parsed = json.loads(add_json) if isinstance(add_json, str) else add_json
                if not isinstance(parsed, list):
                    parsed = []
            except Exception:
                parsed = []
            # Armazenar em campo observacoes como fallback até ter modelo próprio
            if parsed:
                from datetime import datetime

                prefix = f"\n[Endereços Adicionais {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"
                payload["observacoes"] = (
                    (payload.get("observacoes") or "")
                    + prefix
                    + "\n".join(
                        [
                            f"- {item.get('tipo', '?')}: {item.get('logradouro', '')} {item.get('numero', '')} - {item.get('cidade', '')}/{item.get('uf', '')}"
                            for item in parsed
                        ]
                    )
                )
            payload.pop("additional_addresses_json", None)

        required = ["nome_completo", "cpf", "data_nascimento", "data_admissao", "cargo", "salario_base"]
        missing = [r for r in required if r not in payload or payload[r] in (None, "")]
        if missing:
            messages.error(self.request, _("Campos obrigatórios faltando: ") + ", ".join(missing))
            self.set_current_step(1)
            return redirect(self.get_step_url(1))

        if not editing_instance and Funcionario.objects.filter(tenant=tenant, cpf=payload["cpf"]).exists():
            messages.error(self.request, _("Já existe funcionário com este CPF."))
            self.set_current_step(1)
            return redirect(self.get_step_url(1))

        try:
            with transaction.atomic():
                if editing_instance:
                    funcionario = self.persist_editing_instance(editing_instance)
                    # Garantir tenant
                    if not funcionario.tenant_id:
                        funcionario.tenant = tenant
                        funcionario.save(update_fields=["tenant"])
                    messages.success(self.request, _("Funcionário atualizado com sucesso."))
                else:
                    funcionario = Funcionario.objects.create(
                        tenant=tenant,
                        **{k: v for k, v in payload.items() if k in [f.name for f in Funcionario._meta.fields]},
                    )
                    # Histórico inicial
                    with contextlib.suppress(Exception):
                        SalarioHistorico.objects.create(
                            tenant=tenant,
                            funcionario=funcionario,
                            data_vigencia=payload.get("data_admissao") or funcionario.data_admissao,
                            valor_salario=funcionario.salario_base,
                            motivo_alteracao="Salário inicial",
                        )
                    # Horários detalhados
                    horarios_json = payload.get("horarios_json")
                    if horarios_json:
                        self.apply_horarios_from_json(funcionario, horarios_json)

                    # Dependentes (JSON)
                    dependentes_json = payload.get("dependentes_json")
                    if dependentes_json:
                        import json

                        try:
                            deps = json.loads(dependentes_json)
                            if isinstance(deps, list):
                                # Ao criar simplesmente insere; ao editar (ramo acima) será tratado separadamente
                                from .models import Dependente

                                dep_objs = []
                                for d in deps:
                                    try:
                                        nome = d.get("nome") or d.get("nome_completo")
                                        if not nome:
                                            continue
                                        dep_objs.append(
                                            Dependente(
                                                tenant=tenant,
                                                funcionario=funcionario,
                                                nome_completo=nome,
                                                cpf=d.get("cpf") or None,
                                                data_nascimento=d.get("data_nascimento") or d.get("nascimento"),
                                                tipo_dependente=d.get("tipo") or d.get("tipo_dependente") or "OUTRO",
                                                dependente_ir=bool(d.get("ir", True)),
                                                dependente_salario_familia=bool(d.get("salario_familia", True)),
                                            )
                                        )
                                    except Exception:
                                        continue
                                # Converter datas se string
                                from datetime import datetime

                                for o in dep_objs:
                                    if isinstance(o.data_nascimento, str) and o.data_nascimento:
                                        try:
                                            o.data_nascimento = datetime.strptime(o.data_nascimento, "%Y-%m-%d").date()
                                        except Exception:
                                            from datetime import date

                                            o.data_nascimento = date.today()
                                if dep_objs:
                                    from django.db import transaction

                                    with transaction.atomic():
                                        from .models import Dependente as Dp

                                        Dp.objects.bulk_create(dep_objs)
                        except Exception:
                            pass
                    messages.success(self.request, _("Funcionário criado com sucesso."))
            self.clear_wizard()
            return redirect("funcionarios:funcionario_detail", pk=funcionario.pk)
        except Exception as e:
            messages.error(self.request, _("Erro ao criar funcionário: ") + str(e))
            return redirect(self.get_step_url(1))


def funcionario_wizard_create(request):
    return FuncionarioWizardView.as_view()(request)


def funcionario_wizard_goto_step(request, step: int):
    try:
        step = int(step)
    except (ValueError, TypeError):
        step = 1
    request.session["funcionario_wizard_step"] = step
    request.session.modified = True
    return redirect("funcionarios:funcionario_wizard_create")


def funcionario_wizard_edit(request, pk: int):
    return FuncionarioWizardView.as_view()(request, pk=pk)


def funcionario_wizard_goto_step_edit(request, step: int, pk: int):
    try:
        step = int(step)
    except (ValueError, TypeError):
        step = 1
    request.session["funcionario_wizard_step"] = step
    request.session.modified = True
    return redirect("funcionarios:funcionario_wizard_edit", pk=pk)

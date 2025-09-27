"""Formulários do Wizard de criação de Tenant.

Este módulo contém os formulários e widgets usados nas etapas do wizard.
"""

# core/wizard_forms.py - Formulários do Wizard de Criação de Tenant (VERSÃO INDEPENDENTE)
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.forms.widgets import Widget
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from core.models import Tenant
from core.validators import RESERVED_SUBDOMAINS, SUBDOMAIN_REGEX, normalize_subdomain

if TYPE_CHECKING:  # Tipagem apenas; evita ImportError em runtime no Django 5+
    from django.utils.safestring import SafeText


class EditingTenantMixin:
    """Mixin para disponibilizar o método set_editing_tenant_pk em formulários."""

    def set_editing_tenant_pk(self, tenant_pk: int | None) -> None:
        """Define o PK do tenant em edição para validações de unicidade."""
        self._editing_tenant_pk = tenant_pk


class MultipleFileInput(Widget):
    """Widget customizado para upload de múltiplos arquivos.

    Padrão Ultra Moderno - Implementação completa do zero.
    """

    template_name = "django/forms/widgets/file.html"

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        """Inicializa o widget permitindo múltiplos arquivos e classes CSS padrão."""
        if attrs is None:
            attrs = {}

        # Atributos padrão para o widget ultra-moderno
        default_attrs = {
            "multiple": True,
            "class": "form-control wizard-field multiple-file-input",
            "accept": "*/*",  # Aceita todos os tipos por padrão
        }
        default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, _value: object) -> None:
        """Formata o valor para exibição; inputs de arquivo não exibem valor."""
        return

    def value_from_datadict(
        self,
        _data: Mapping[str, object],
        files: Mapping[str, object],
        name: str,
    ) -> UploadedFile | Sequence[UploadedFile] | None:
        """Extrai múltiplos arquivos do request com fallback seguro para single file."""
        result: UploadedFile | Sequence[UploadedFile] | None = None
        upload_obj: object | None = None
        getlist = getattr(files, "getlist", None)
        if callable(getlist):
            try:
                upload_obj = getlist(name)
            except Exception:  # noqa: BLE001
                upload_obj = None

        if upload_obj is None:
            single = files.get(name)
            result = single if isinstance(single, UploadedFile) else None
        elif isinstance(upload_obj, (list, tuple)):
            if upload_obj:
                if len(upload_obj) == 1 and isinstance(upload_obj[0], UploadedFile):
                    result = upload_obj[0]
                else:
                    seq: list[UploadedFile] = [f for f in upload_obj if isinstance(f, UploadedFile)]
                    result = seq or None
            else:
                result = None
        elif isinstance(upload_obj, UploadedFile):
            result = upload_obj
        else:
            result = None
        return result

    def render(
        self,
        name: str,
        _value: object | None,
        attrs: dict[str, Any] | None = None,
        _renderer: object | None = None,
    ) -> "SafeText":
        """Renderiza o widget de múltiplos arquivos com padrão ultra-moderno."""
        if attrs is None:
            attrs = {}

        final_attrs = self.build_attrs(self.attrs, attrs)
        final_attrs["type"] = "file"
        final_attrs["name"] = name

        # Construir HTML manualmente para controle total
        attr_strings = []
        for key, val in final_attrs.items():
            if val is True:
                attr_strings.append(f"{key}")
            elif val is not False and val is not None:
                attr_strings.append(f'{key}="{val}"')

        attrs_str = " ".join(attr_strings)

        html = f"""
        <div class="multiple-file-upload-container">
            <input {attrs_str} />
            <div class="file-preview-container mt-2" style="display: none;">
                <small class="text-muted">Arquivos selecionados:</small>
                <ul class="file-list list-unstyled mt-1"></ul>
            </div>
        </div>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.multiple-file-upload-container').forEach(function(container) {{
                const input = container.querySelector('input[type="file"]');
                if (!input) return;
                const previewContainer = container.querySelector('.file-preview-container');
                const fileList = container.querySelector('.file-list');
                input.addEventListener('change', function() {{
                    fileList.innerHTML = '';
                    if (this.files && this.files.length > 0) {{
                        previewContainer.style.display = 'block';
                        Array.from(this.files).forEach(function(file) {{
                            const li = document.createElement('li');
                            li.className = 'small text-info';
                            const icon = document.createElement('i');
                            icon.className = 'fas fa-file';
                            const sizeKb = (file.size / 1024).toFixed(1);
                            const text = document.createTextNode(
                                ' ' + file.name + ' (' + sizeKb + ' KB)'
                            );
                            li.appendChild(icon);
                            li.appendChild(text);
                            fileList.appendChild(li);
                        }});
                    }} else {{
                        previewContainer.style.display = 'none';
                    }}
                }});
            }});
        }});
        </script>
        """
        return mark_safe(html)  # noqa: S308


class MultipleFileField(forms.FileField):
    """Campo customizado para múltiplos arquivos.

    Padrão Ultra Moderno - Validação e processamento completo.
    """

    widget = MultipleFileInput

    def _coerce_to_list(
        self,
        data: UploadedFile | Sequence[UploadedFile] | None,
    ) -> list[UploadedFile]:
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [f for f in data if isinstance(f, UploadedFile)]
        return [data] if isinstance(data, UploadedFile) else []

    def _validate_limits(self, files: list[UploadedFile]) -> None:
        max_files = self.max_files
        if isinstance(max_files, int) and len(files) > max_files:
            msg = f"Máximo de {max_files} arquivos permitidos. Você selecionou {len(files)}."
            raise ValidationError(msg)

    def _validate_single_file(
        self,
        item: UploadedFile,
        initial: UploadedFile | None,
    ) -> UploadedFile | None:
        validated_file = super().clean(item, initial)
        if not validated_file:
            return validated_file
        types_set = self.file_types
        if isinstance(types_set, set):
            file_extension = validated_file.name.split(".")[-1].lower()
            if file_extension not in types_set:
                msg = (
                    f"Tipo de arquivo não permitido: {file_extension}. Tipos permitidos: {', '.join(sorted(types_set))}"
                )
                raise ValidationError(msg)
        if self.max_file_size and getattr(validated_file, "size", None) and validated_file.size > self.max_file_size:
            max_mb = int(self.max_file_size / (1024 * 1024))
            msg = f"Tamanho máximo por arquivo excedido ({max_mb} MB)."
            raise ValidationError(msg)
        return validated_file

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Extrai limites e inicializa o campo com widget customizado."""
        # Extrair configurações específicas para múltiplos arquivos
        max_files_val = kwargs.pop("max_files", None)
        self.max_files: int | None = max_files_val if isinstance(max_files_val, int) else None

        file_types_val = kwargs.pop("file_types", None)
        if file_types_val is None:
            self.file_types: set[str] | None = None
        else:
            try:
                iterable = file_types_val if isinstance(file_types_val, (list, set, tuple)) else []
                self.file_types = {str(x).lower().lstrip(".") for x in iterable}
            except Exception:  # noqa: BLE001
                self.file_types = None

        # Tamanho máximo por arquivo (padrão 10MB)
        max_size_val = kwargs.pop("max_file_size", 10 * 1024 * 1024)
        self.max_file_size: int = max_size_val if isinstance(max_size_val, int) else 10 * 1024 * 1024

        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(
        self,
        data: UploadedFile | Sequence[UploadedFile] | None,
        initial: UploadedFile | None = None,
    ) -> list[UploadedFile]:
        """Valida múltiplos arquivos com verificações avançadas."""
        # Se não há dados e o campo não é obrigatório
        if not data and not self.required:
            return []

        # Se não há dados e o campo é obrigatório
        if not data and self.required:
            raise ValidationError(self.error_messages["required"])

        files = self._coerce_to_list(data)

        # Verificar limite máximo de arquivos
        self._validate_limits(files)

        # Valida cada arquivo individualmente
        result = []
        for i, item in enumerate(files):
            if item:  # Apenas processar se o item não é None/vazio
                try:
                    validated_file = self._validate_single_file(item, initial)
                    if validated_file:
                        result.append(validated_file)
                except ValidationError as e:
                    # Re-lançar erros de validação com contexto do arquivo
                    msg = f"Arquivo {i + 1}: {e!s}"
                    raise ValidationError(msg) from e

        return result


class TenantPessoaFisicaWizardForm(EditingTenantMixin, forms.ModelForm):
    """📋 PESSOA FÍSICA COMPLETO.

    ├── tipo_pessoa (sempre PF)
    ├── name (nome completo da pessoa)
    ├── email (email da pessoa)
    ├── telefone (telefone da pessoa)
    └── + 11 campos específicos PF (CPF, RG, data_nascimento, etc.)
    """

    class Meta:
        """Metadados do formulário de Pessoa Física."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            "tipo_pessoa",
            "name",
            "email",
            "telefone",
            "cpf",
            "rg",
            "data_nascimento",
            "sexo",
            "estado_civil",
            "nacionalidade",
            "naturalidade",
            "nome_mae",
            "nome_pai",
            "profissao",
            "escolaridade",
        ]

    widgets: ClassVar[dict[str, forms.Widget]] = {
        "tipo_pessoa": forms.HiddenInput(attrs={"value": "PF", "id": "id_pf_tipo_pessoa"}),
        "name": forms.TextInput(
            attrs={
                "class": "form-control wizard-field",
                "placeholder": "Nome Completo da Pessoa",
                "id": "id_pf_name",
            },
        ),
        "email": forms.EmailInput(
            attrs={
                "class": "form-control wizard-field",
                "placeholder": "email.pessoal@dominio.com",
                "id": "id_pf_email",
            },
        ),
        "telefone": forms.TextInput(
            attrs={
                "class": "form-control wizard-field phone-mask",
                "placeholder": "(99) 99999-9999",
                "id": "id_pf_telefone",
            },
        ),
        "cpf": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field cpf-mask", "placeholder": "999.999.999-99"},
        ),
        "rg": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "Número do RG"},
        ),
        "data_nascimento": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field datepicker", "placeholder": "DD/MM/AAAA"},
        ),
        "sexo": forms.Select(attrs={"class": "form-select wizard-field wizard-pf-field"}),
        "estado_civil": forms.Select(attrs={"class": "form-select wizard-field wizard-pf-field"}),
        "nacionalidade": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "País de nacionalidade"},
        ),
        "naturalidade": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "Cidade de nascimento"},
        ),
        "nome_mae": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "Nome completo da mãe"},
        ),
        "nome_pai": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "Nome completo do pai"},
        ),
        "profissao": forms.TextInput(
            attrs={"class": "form-control wizard-field wizard-pf-field", "placeholder": "Engenheiro, Médico..."},
        ),
        "escolaridade": forms.Select(attrs={"class": "form-select wizard-field wizard-pf-field"}),
    }

    labels: ClassVar[dict[str, str]] = {
        "tipo_pessoa": _("Tipo de Pessoa"),
        "name": _("Nome Completo"),
        "email": _("E-mail"),
        "telefone": _("Telefone"),
        "cpf": _("CPF"),
        "rg": _("RG"),
        "data_nascimento": _("Data de Nascimento"),
        "sexo": _("Sexo"),
        "estado_civil": _("Estado Civil"),
        "nacionalidade": _("Nacionalidade"),
        "naturalidade": _("Naturalidade"),
        "nome_mae": _("Nome da Mãe"),
        "nome_pai": _("Nome do Pai"),
        "profissao": _("Profissão"),
        "escolaridade": _("Escolaridade"),
    }

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Inicializa o formulário e configura campos/formatos padrão."""
        pk_obj = kwargs.pop("editing_tenant_pk", None)
        self._editing_tenant_pk: int | None = pk_obj if isinstance(pk_obj, int) else None
        super().__init__(*args, **kwargs)

        # Forçar tipo_pessoa = PF
        self.fields["tipo_pessoa"].initial = "PF"

        # Configurar campos obrigatórios
        self.fields["name"].required = True
        self.fields["cpf"].required = True

        # Datas: aceitar pt-BR e ISO
        if "data_nascimento" in self.fields:
            field = self.fields["data_nascimento"]
            if isinstance(field, forms.DateField):
                field.input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
            # Ajustar widget para DateInput mantendo aparência
            self.fields["data_nascimento"].widget = forms.DateInput(
                format="%d/%m/%Y",
                attrs={
                    "class": "form-control wizard-field wizard-pf-field datepicker",
                    "placeholder": "DD/MM/AAAA",
                    "autocomplete": "off",
                    "type": "text",
                },
            )

    def clean_tipo_pessoa(self) -> str:
        """Garante que o tipo de pessoa seja PF."""
        value = self.cleaned_data.get("tipo_pessoa") or "PF"
        if value != "PF":
            raise forms.ValidationError(_("Tipo de pessoa inválido para este formulário."))
        return "PF"

    def clean_cpf(self) -> str | None:
        """Validação de CPF única com normalização básica."""
        cpf = self.cleaned_data.get("cpf")
        if cpf:
            cpf_digits = re.sub(r"\D", "", str(cpf))
            # Checagem simples de tamanho (opcional implementar algoritmo completo)
            if len(cpf_digits) not in (11,):
                raise forms.ValidationError(_("CPF inválido."))
            queryset = Tenant.objects.filter(Q(cpf=cpf) | Q(cpf=cpf_digits))
            if self._editing_tenant_pk:
                queryset = queryset.exclude(pk=self._editing_tenant_pk)
            elif self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(_("Este CPF já está cadastrado."))
        return cpf


class TenantPessoaJuridicaWizardForm(EditingTenantMixin, forms.ModelForm):
    """📋 PESSOA JURÍDICA COMPLETO.

    ├── tipo_pessoa (sempre PJ)
    ├── name (nome fantasia da empresa)
    ├── email (email da empresa)
    ├── telefone (telefone da empresa)
    └── + 10 campos específicos PJ (CNPJ, razão_social, etc.)
    """

    class Meta:
        """Metadados do formulário de Pessoa Jurídica."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            "tipo_pessoa",
            "name",
            "email",
            "telefone",
            "razao_social",
            "cnpj",
            "inscricao_estadual",
            "inscricao_municipal",
            "data_fundacao",
            "ramo_atividade",
            "porte_empresa",
            "cnae_principal",
            "regime_tributario",
        ]

        widgets: ClassVar[dict[str, forms.Widget]] = {
            "tipo_pessoa": forms.HiddenInput(attrs={"value": "PJ", "id": "id_pj_tipo_pessoa"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control wizard-field",
                    "placeholder": "Nome Fantasia da Empresa",
                    "id": "id_pj_name",
                },
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control wizard-field",
                    "placeholder": "email.empresa@dominio.com",
                    "id": "id_pj_email",
                },
            ),
            "telefone": forms.TextInput(
                attrs={
                    "class": "form-control wizard-field phone-mask",
                    "placeholder": "(99) 99999-9999",
                    "id": "id_pj_telefone",
                },
            ),
            "razao_social": forms.TextInput(
                attrs={
                    "class": "form-control wizard-field wizard-pj-field",
                    "placeholder": "Nome de registro da empresa",
                },
            ),
            "cnpj": forms.TextInput(
                attrs={
                    "class": "form-control wizard-field wizard-pj-field cnpj-mask",
                    "placeholder": "99.999.999/9999-99",
                },
            ),
            "inscricao_estadual": forms.TextInput(
                attrs={"class": "form-control wizard-field wizard-pj-field", "placeholder": "Número da I.E."},
            ),
            "inscricao_municipal": forms.TextInput(
                attrs={"class": "form-control wizard-field wizard-pj-field", "placeholder": "Número da I.M."},
            ),
            "data_fundacao": forms.TextInput(
                attrs={"class": "form-control wizard-field wizard-pj-field datepicker", "placeholder": "DD/MM/AAAA"},
            ),
            "ramo_atividade": forms.TextInput(
                attrs={"class": "form-control wizard-field wizard-pj-field", "placeholder": "Ex: Construção Civil"},
            ),
            "porte_empresa": forms.Select(attrs={"class": "form-select wizard-field wizard-pj-field"}),
            "cnae_principal": forms.TextInput(
                attrs={"class": "form-control wizard-field wizard-pj-field", "placeholder": "Ex: 4120-4/00"},
            ),
            "regime_tributario": forms.Select(attrs={"class": "form-select wizard-field wizard-pj-field"}),
        }

        labels: ClassVar[dict[str, str]] = {
            "tipo_pessoa": _("Tipo de Pessoa"),
            "name": _("Nome Fantasia"),
            "email": _("E-mail da Empresa"),
            "telefone": _("Telefone da Empresa"),
            "razao_social": _("Razão Social"),
            "cnpj": _("CNPJ"),
            "inscricao_estadual": _("Inscrição Estadual"),
            "inscricao_municipal": _("Inscrição Municipal"),
            "data_fundacao": _("Data de Fundação"),
            "ramo_atividade": _("Ramo de Atividade"),
            "porte_empresa": _("Porte da Empresa"),
            "cnae_principal": _("CNAE Principal"),
            "regime_tributario": _("Regime Tributário"),
        }

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Inicializa o formulário e configura campos/formatos padrão."""
        self._editing_tenant_pk = kwargs.pop("editing_tenant_pk", None)
        super().__init__(*args, **kwargs)

        # Forçar tipo_pessoa = PJ
        self.fields["tipo_pessoa"].initial = "PJ"

        # Configurar campos obrigatórios
        self.fields["name"].required = True
        self.fields["razao_social"].required = True
        self.fields["cnpj"].required = True

        # Datas: aceitar pt-BR e ISO
        if "data_fundacao" in self.fields:
            field = self.fields["data_fundacao"]
            if isinstance(field, forms.DateField):
                field.input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
            self.fields["data_fundacao"].widget = forms.DateInput(
                format="%d/%m/%Y",
                attrs={
                    "class": "form-control wizard-field wizard-pj-field datepicker",
                    "placeholder": "DD/MM/AAAA",
                    "autocomplete": "off",
                    "type": "text",
                },
            )

    def clean_tipo_pessoa(self) -> str:
        """Garante que o tipo de pessoa seja PJ."""
        value = self.cleaned_data.get("tipo_pessoa") or "PJ"
        if value != "PJ":
            raise forms.ValidationError(_("Tipo de pessoa inválido para este formulário."))
        return "PJ"

    def clean_cnpj(self) -> str | None:
        """Validação de CNPJ única com normalização básica."""
        cnpj = self.cleaned_data.get("cnpj")
        if cnpj:
            cnpj_digits = re.sub(r"\D", "", str(cnpj))
            if len(cnpj_digits) not in (14,):
                raise forms.ValidationError(_("CNPJ inválido."))
            queryset = Tenant.objects.filter(Q(cnpj=cnpj) | Q(cnpj=cnpj_digits))
            if self._editing_tenant_pk:
                queryset = queryset.exclude(pk=self._editing_tenant_pk)
            elif self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(_("Este CNPJ já está cadastrado."))
        return cnpj


# Formulários de Endereço, Contatos e Demais Steps


class TenantAddressWizardForm(forms.Form):
    """STEP 2: Endereço Principal."""

    # Campo oculto para manter a lista de endereços adicionais em JSON
    # Estrutura esperada:
    # [ { tipo:'COB'|'ENT'|'FISCAL'|'OUTRO', logradouro:'', numero:'', ... , principal: true|false }, ... ]
    additional_addresses_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"class": "wizard-additional-addresses-json"}),
        initial="[]",
        label=_("Endereços adicionais (JSON)"),
    )

    cep = forms.CharField(
        max_length=10,
        label=_("CEP"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field cep-mask", "placeholder": "00000-000"}),
    )

    logradouro = forms.CharField(
        max_length=255,
        label=_("Logradouro"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Rua, Avenida, etc."}),
    )

    numero = forms.CharField(
        max_length=10,
        label=_("Número"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "123"}),
    )

    complemento = forms.CharField(
        max_length=100,
        required=False,
        label=_("Complemento"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Apto, Sala, etc."}),
    )

    bairro = forms.CharField(
        max_length=100,
        label=_("Bairro"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Bairro"}),
    )

    cidade = forms.CharField(
        max_length=100,
        label=_("Cidade"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Cidade"}),
    )

    uf = forms.ChoiceField(
        choices=[
            ("", "Selecione o Estado..."),
            ("AC", "Acre"),
            ("AL", "Alagoas"),
            ("AP", "Amapá"),
            ("AM", "Amazonas"),
            ("BA", "Bahia"),
            ("CE", "Ceará"),
            ("DF", "Distrito Federal"),
            ("ES", "Espírito Santo"),
            ("GO", "Goiás"),
            ("MA", "Maranhão"),
            ("MT", "Mato Grosso"),
            ("MS", "Mato Grosso do Sul"),
            ("MG", "Minas Gerais"),
            ("PA", "Pará"),
            ("PB", "Paraíba"),
            ("PR", "Paraná"),
            ("PE", "Pernambuco"),
            ("PI", "Piauí"),
            ("RJ", "Rio de Janeiro"),
            ("RN", "Rio Grande do Norte"),
            ("RS", "Rio Grande do Sul"),
            ("RO", "Rondônia"),
            ("RR", "Roraima"),
            ("SC", "Santa Catarina"),
            ("SP", "São Paulo"),
            ("SE", "Sergipe"),
            ("TO", "Tocantins"),
        ],
        label=_("Estado (UF)"),
        widget=forms.Select(attrs={"class": "form-select wizard-field"}),
    )

    pais = forms.CharField(
        max_length=100,
        initial="Brasil",
        label=_("País"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field"}),
    )

    ponto_referencia = forms.CharField(
        max_length=200,
        required=False,
        label=_("Ponto de Referência"),
        widget=forms.TextInput(
            attrs={
                "class": "form-control wizard-field",
                "placeholder": "Ex: Próximo ao shopping, em frente à escola",
            },
        ),
    )

    def clean_additional_addresses_json(self) -> str:
        """Garante JSON válido (lista) e retorna string normalizada."""
        data = self.cleaned_data.get("additional_addresses_json")
        if not data:
            return "[]"
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                # Normalizar para lista vazia se estrutura inesperada
                return "[]"
            # Opcional: limitar tamanho para evitar payloads excessivos
            max_addresses = 50
            if len(parsed) > max_addresses:
                parsed = parsed[:max_addresses]
            return json.dumps(parsed, ensure_ascii=False)
        except (TypeError, ValueError):
            # Em caso de erro de JSON, retornar lista vazia para não quebrar navegação livre
            return "[]"


class TenantContactsWizardForm(forms.ModelForm):
    """STEP 3: Contatos, Website e Redes Sociais."""

    # Campos adicionais para contato principal (não estão no modelo)
    cargo_contato_principal = forms.CharField(
        required=False,
        label=_("Cargo"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Ex: Diretor, Gerente"}),
    )
    email_contato_principal = forms.EmailField(
        required=False,
        label=_("E-mail do Contato"),
        widget=forms.EmailInput(attrs={"class": "form-control wizard-field", "placeholder": "contato@empresa.com"}),
    )
    telefone_contato_principal = forms.CharField(
        required=False,
        label=_("Telefone do Contato"),
        widget=forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 98765-4321"},
        ),
    )

    # Campos adicionais para contatos departamentais (não estão no modelo)
    cargo_responsavel_comercial = forms.CharField(
        required=False,
        label=_("Cargo"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Ex: Diretor, Gerente"}),
    )
    cargo_responsavel_financeiro = forms.CharField(
        required=False,
        label=_("Cargo"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Ex: Diretor, Gerente"}),
    )

    # Campos para redes sociais: substituídos por coleção dinâmica via socials_json
    # Mantivemos os campos antigos comentados para referência; a UI não os utiliza mais.
    # Campos para redes sociais foram substituídos por coleção dinâmica via socials_json.

    # Website removido da UI neste step

    # Novo: coleção de múltiplos contatos livres (JSON serializado)
    # Estrutura esperada: [{"nome": "...", "email": "...", "telefone": "...", "cargo": "...", "observacao": "..."}, ...]
    contacts_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"class": "wizard-multi-contacts-json"}),
        help_text=_("Coleção de contatos adicionais em formato JSON (gerenciado via UI dinâmica)."),
    )

    # Novo: coleção dinâmica de redes sociais (nome/link) em JSON
    # Estrutura esperada: [{"nome": "Instagram", "link": "https://instagram.com/empresa"}, ...]
    socials_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"class": "wizard-socials-json"}),
        help_text=_("Coleção de redes sociais em formato JSON (gerenciado via UI dinâmica)."),
    )

    class Meta:
        """Metadados do formulário de contatos e redes sociais."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            # Contato Principal
            "nome_contato_principal",
            # Contatos Departamentais
            "nome_responsavel_comercial",
            "email_comercial",
            "telefone_comercial",
            "nome_responsavel_financeiro",
            "email_financeiro",
            "telefone_financeiro",
            # Contato de Emergência
            "telefone_emergencia",
            # Hidden para múltiplos contatos
            "contacts_json",
            # Hidden para redes sociais dinâmicas
            "socials_json",
        ]

    widgets: ClassVar[dict[str, forms.Widget]] = {
        # Contato Principal
        "nome_contato_principal": forms.TextInput(
            attrs={"class": "form-control wizard-field", "placeholder": "Nome completo do responsável"},
        ),
        # Contatos Departamentais
        "nome_responsavel_comercial": forms.TextInput(
            attrs={"class": "form-control wizard-field", "placeholder": "Nome do responsável"},
        ),
        "email_comercial": forms.EmailInput(
            attrs={"class": "form-control wizard-field", "placeholder": "comercial@empresa.com"},
        ),
        "telefone_comercial": forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"},
        ),
        "nome_responsavel_financeiro": forms.TextInput(
            attrs={"class": "form-control wizard-field", "placeholder": "Nome do responsável"},
        ),
        "email_financeiro": forms.EmailInput(
            attrs={"class": "form-control wizard-field", "placeholder": "financeiro@empresa.com"},
        ),
        "telefone_financeiro": forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"},
        ),
        # Contato de Emergência
        "telefone_emergencia": forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"},
        ),
    }

    def clean_contacts_json(self) -> str:
        """Valida e normaliza a coleção de contatos em JSON."""
        raw = self.cleaned_data.get("contacts_json")
        if not raw:
            return "[]"
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return "[]"
            # Normalização básica + limites de segurança
            normalized = []
            max_contacts = 100
            for item in data[:max_contacts]:  # limitar a 100 contatos
                if not isinstance(item, dict):
                    continue
                nome = (item.get("nome") or "").strip()
                email = (item.get("email") or "").strip()
                telefone = (item.get("telefone") or "").strip()
                cargo = (item.get("cargo") or "").strip()
                observacao = (item.get("observacao") or "").strip()
                # Pelo menos um identificador mínimo (nome ou email ou telefone)
                if not (nome or email or telefone):
                    continue
                normalized.append(
                    {
                        "nome": nome[:100],
                        "email": email[:254],
                        "telefone": telefone[:20],
                        "cargo": cargo[:100] or None,
                        "observacao": observacao[:500] or None,
                    },
                )
            return json.dumps(normalized, ensure_ascii=False)
        except (TypeError, ValueError):
            return "[]"

    def clean_socials_json(self) -> str:
        """Valida e normaliza a coleção de redes sociais em JSON."""
        raw = self.cleaned_data.get("socials_json")
        if not raw:
            return "[]"
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return "[]"
            normalized = []
            max_socials = 50
            for item in data[:max_socials]:  # limitar a 50 redes sociais
                if not isinstance(item, dict):
                    continue
                nome = (item.get("nome") or "").strip()
                link = (item.get("link") or "").strip()
                if not (nome and link):
                    continue
                # Normalizar esquema do link
                parsed = urlparse(link)
                if not parsed.scheme:
                    link = "https://" + link
                normalized.append(
                    {
                        "nome": nome[:50],
                        "link": link[:500],
                    },
                )
            return json.dumps(normalized, ensure_ascii=False)
        except (TypeError, ValueError):
            return "[]"


## Removido: Step de Documentos agora é totalmente conduzido via API (app documentos)


class TenantConfigurationWizardForm(EditingTenantMixin, forms.ModelForm):
    """STEP 5: Configurações & Módulos."""

    # Definição completa dos módulos disponíveis (igual ao forms.py)
    AVAILABLE_MODULES: ClassVar[dict[str, dict[str, object]]] = {
        # Módulos Básicos de Gestão
        "clientes": {
            "name": "Clientes",
            "description": "Gestão completa de clientes, contratos e relacionamentos",
            "category": "Gestão Básica",
            "premium": False,
        },
        "fornecedores": {
            "name": "Fornecedores",
            "description": "Cadastro e gestão de fornecedores e parcerias",
            "category": "Gestão Básica",
            "premium": False,
        },
        "produtos": {
            "name": "Produtos",
            "description": "Catálogo de produtos, preços e especificações",
            "category": "Gestão Básica",
            "premium": False,
        },
        "servicos": {
            "name": "Serviços",
            "description": "Gestão de serviços oferecidos pela empresa",
            "category": "Gestão Básica",
            "premium": False,
        },
        "funcionarios": {
            "name": "Funcionários",
            "description": "Gestão de recursos humanos e colaboradores",
            "category": "Gestão Básica",
            "premium": False,
        },
        "cadastros_gerais": {
            "name": "Cadastros Gerais",
            "description": "Cadastros auxiliares e configurações gerais",
            "category": "Gestão Básica",
            "premium": False,
        },
        # Módulos de Obras e Projetos
        "obras": {
            "name": "Obras",
            "description": "Gestão completa de obras e projetos de construção",
            "category": "Obras e Projetos",
            "premium": False,
        },
        "orcamentos": {
            "name": "Orçamentos",
            "description": "Criação e gestão de orçamentos detalhados",
            "category": "Obras e Projetos",
            "premium": False,
        },
        "quantificacao_obras": {
            "name": "Quantificação de Obras",
            "description": "Cálculos e quantificações para projetos",
            "category": "Obras e Projetos",
            "premium": True,
        },
        "apropriacao": {
            "name": "Apropriação",
            "description": "Apropriação de custos e controle de obras",
            "category": "Obras e Projetos",
            "premium": True,
        },
        "mao_obra": {
            "name": "Mão de Obra",
            "description": "Gestão de equipes e mão de obra especializada",
            "category": "Obras e Projetos",
            "premium": False,
        },
        # Módulos Financeiros e Operacionais
        "compras": {
            "name": "Compras",
            "description": "Sistema de compras, cotações e aquisições",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "financeiro": {
            "name": "Financeiro",
            "description": "Controle financeiro completo da empresa",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "estoque": {
            "name": "Estoque",
            "description": "Controle de estoque e movimentações",
            "category": "Financeiro e Operacional",
            "premium": False,
        },
        "aprovacoes": {
            "name": "Aprovações",
            "description": "Sistema de workflow e aprovações",
            "category": "Financeiro e Operacional",
            "premium": True,
        },
        # Módulos de Saúde e Clínicas
        "prontuarios": {
            "name": "Prontuários",
            "description": "Prontuários médicos eletrônicos",
            "category": "Saúde e Clínicas",
            "premium": True,
        },
        "sst": {
            "name": "SST",
            "description": "Segurança e Saúde do Trabalho",
            "category": "Saúde e Clínicas",
            "premium": True,
        },
        # Módulos de Comunicação e Organização
        "agenda": {
            "name": "Agenda",
            "description": "Agenda compartilhada e agendamentos",
            "category": "Comunicação e Organização",
            "premium": False,
        },
        "agendamentos": {
            "name": "Agendamentos Avançados",
            "description": "Regras e serviços de agendamento (módulo separado)",
            "category": "Comunicação e Organização",
            "premium": False,
        },
        "chat": {
            "name": "Chat",
            "description": "Chat interno em tempo real",
            "category": "Comunicação e Organização",
            "premium": True,
        },
        "notifications": {
            "name": "Notificações",
            "description": "Sistema de notificações e alertas",
            "category": "Comunicação e Organização",
            "premium": False,
        },
        # Módulos de Formulários e Documentação
        "formularios": {
            "name": "Formulários",
            "description": "Formulários customizados para a empresa",
            "category": "Formulários e Documentação",
            "premium": False,
        },
        "formularios_dinamicos": {
            "name": "Formulários Dinâmicos",
            "description": "Criador avançado de formulários dinâmicos",
            "category": "Formulários e Documentação",
            "premium": True,
        },
        # Módulos de Capacitação e Gestão
        "treinamento": {
            "name": "Treinamentos",
            "description": "Sistema de treinamentos e capacitação",
            "category": "Capacitação e Gestão",
            "premium": True,
        },
        "user_management": {
            "name": "Gestão de Usuários",
            "description": "Gestão avançada de usuários e permissões",
            "category": "Capacitação e Gestão",
            "premium": False,
        },
        # Módulos de Análise e Inteligência
        "relatorios": {
            "name": "Relatórios",
            "description": "Sistema completo de relatórios",
            "category": "Análise e Inteligência",
            "premium": False,
        },
        "bi": {
            "name": "Business Intelligence",
            "description": "Dashboards e análises inteligentes",
            "category": "Análise e Inteligência",
            "premium": True,
        },
        "ai_auditor": {
            "name": "Auditor IA",
            "description": "Auditoria automatizada com inteligência artificial",
            "category": "Análise e Inteligência",
            "premium": True,
        },
        # Módulos Administrativos
        "admin": {
            "name": "Dashboard Admin",
            "description": "Painel administrativo avançado",
            "category": "Administrativo",
            "premium": False,
        },
        # Portais e Assistentes
        "portal_cliente": {
            "name": "Portal do Cliente",
            "description": "Acesso para clientes acompanharem informações e interações",
            "category": "Portais Externos",
            "premium": False,
        },
        "portal_fornecedor": {
            "name": "Portal do Fornecedor",
            "description": "Colaboração com fornecedores e cotações",
            "category": "Portais Externos",
            "premium": False,
        },
        "assistente_web": {
            "name": "Assistente Web",
            "description": "Assistente interativo de processos e IA contextual",
            "category": "Suporte e Automação",
            "premium": True,
        },
        "documentos": {
            "name": "Documentos",
            "description": "Gestão de documentos estruturados e regras",
            "category": "Formulários e Documentação",
            "premium": False,
        },
    }

    # Configuração visual dos módulos (ícones e cores)
    MODULE_ICONS_AND_COLORS: ClassVar[dict[str, dict[str, object]]] = {
        # Módulos Básicos de Gestão
        "clientes": {"icon": "fas fa-users", "color": "text-primary", "category": "Gestão Básica"},
        "fornecedores": {"icon": "fas fa-truck", "color": "text-info", "category": "Gestão Básica"},
        "produtos": {"icon": "fas fa-box", "color": "text-success", "category": "Gestão Básica"},
        "servicos": {"icon": "fas fa-tools", "color": "text-warning", "category": "Gestão Básica"},
        "funcionarios": {"icon": "fas fa-id-badge", "color": "text-secondary", "category": "Gestão Básica"},
        "cadastros_gerais": {"icon": "fas fa-database", "color": "text-dark", "category": "Gestão Básica"},
        # Módulos de Obras e Projetos
        "obras": {"icon": "fas fa-hard-hat", "color": "text-primary", "category": "Obras e Projetos"},
        "orcamentos": {"icon": "fas fa-calculator", "color": "text-info", "category": "Obras e Projetos"},
        "quantificacao_obras": {
            "icon": "fas fa-ruler-combined",
            "color": "text-success",
            "category": "Obras e Projetos",
        },
        "apropriacao": {"icon": "fas fa-chart-pie", "color": "text-warning", "category": "Obras e Projetos"},
        "mao_obra": {"icon": "fas fa-users-cog", "color": "text-secondary", "category": "Obras e Projetos"},
        # Módulos Financeiros e Operacionais
        "compras": {"icon": "fas fa-shopping-cart", "color": "text-success", "category": "Financeiro e Operacional"},
        "financeiro": {"icon": "fas fa-dollar-sign", "color": "text-warning", "category": "Financeiro e Operacional"},
        "estoque": {"icon": "fas fa-warehouse", "color": "text-secondary", "category": "Financeiro e Operacional"},
        "aprovacoes": {"icon": "fas fa-check-circle", "color": "text-success", "category": "Financeiro e Operacional"},
        # Módulos de Saúde e Clínicas
        "prontuarios": {"icon": "fas fa-file-medical", "color": "text-danger", "category": "Saúde e Clínicas"},
        "sst": {"icon": "fas fa-shield-alt", "color": "text-danger", "category": "Saúde e Clínicas"},
        # Módulos de Comunicação e Organização
        "agenda": {"icon": "fas fa-calendar", "color": "text-success", "category": "Comunicação e Organização"},
        "agendamentos": {"icon": "fas fa-clock", "color": "text-success", "category": "Comunicação e Organização"},
        "chat": {"icon": "fas fa-comments", "color": "text-warning", "category": "Comunicação e Organização"},
        "notifications": {"icon": "fas fa-bell", "color": "text-info", "category": "Comunicação e Organização"},
        # Módulos de Formulários e Documentação
        "formularios": {"icon": "fas fa-file-alt", "color": "text-secondary", "category": "Formulários e Documentação"},
        "formularios_dinamicos": {
            "icon": "fas fa-magic",
            "color": "text-purple",
            "category": "Formulários e Documentação",
        },
        # Módulos de Capacitação e Gestão
        "treinamento": {"icon": "fas fa-graduation-cap", "color": "text-info", "category": "Capacitação e Gestão"},
        "user_management": {"icon": "fas fa-users-cog", "color": "text-dark", "category": "Capacitação e Gestão"},
        # Módulos de Análise e Inteligência
        "relatorios": {"icon": "fas fa-chart-bar", "color": "text-primary", "category": "Análise e Inteligência"},
        "bi": {"icon": "fas fa-chart-line", "color": "text-info", "category": "Análise e Inteligência"},
        "ai_auditor": {"icon": "fas fa-robot", "color": "text-success", "category": "Análise e Inteligência"},
        # Módulos Administrativos
        "admin": {"icon": "fas fa-tachometer-alt", "color": "text-dark", "category": "Administrativo"},
        # Portais e Assistentes
        "portal_cliente": {"icon": "fas fa-handshake", "color": "text-primary", "category": "Portais Externos"},
        "portal_fornecedor": {"icon": "fas fa-people-carry", "color": "text-primary", "category": "Portais Externos"},
        "assistente_web": {
            "icon": "fas fa-assistive-listening-systems",
            "color": "text-info",
            "category": "Suporte e Automação",
        },
        "documentos": {
            "icon": "fas fa-folder-open",
            "color": "text-secondary",
            "category": "Formulários e Documentação",
        },
    }

    # choices serão montados dinamicamente em __init__ para incluir novos apps internos
    enabled_modules = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label=_("Módulos Habilitados"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input wizard-field"}),
    )

    @classmethod
    def discover_internal_modules(cls) -> list[tuple[str, str]]:
        """Descobre módulos internos a partir de INSTALLED_APPS e diretórios de primeiro nível.

        Regras:
          - Considera apenas apps cujo nome não contém ponto (.) e que tenham diretório no root do projeto.
          - Usa metadados de AVAILABLE_MODULES se existir; caso contrário gera label capitalizada.
        """
        base_dir = getattr(settings, "BASE_DIR", None)
        discovered: list[tuple[str, str]] = []
        if not base_dir:
            return discovered
        root_entries: set[str] = set()
        try:
            for entry in Path(base_dir).iterdir():
                if entry.is_dir() and not entry.name.startswith("_") and entry.name.isidentifier():
                    root_entries.add(entry.name)
        except OSError:
            root_entries = set()
        installed = getattr(settings, "INSTALLED_APPS", [])
        for app in installed:
            base = app.split(".")[0]
            # Se diretório não existe, ainda assim considerar se estiver em AVAILABLE_MODULES
            if base not in root_entries and base not in cls.AVAILABLE_MODULES:
                continue
            meta = cls.AVAILABLE_MODULES.get(base, {})
            label = str(meta.get("name") or base.replace("_", " ").title())
            if (base, label) not in discovered:
                discovered.append((base, label))
        # Adicionar quaisquer módulos definidos manualmente que não estejam na lista mas existem em AVAILABLE_MODULES
        existing_keys = {a for a, _ in discovered}
        for key, meta in cls.AVAILABLE_MODULES.items():
            if key not in existing_keys:
                discovered.append((key, str(meta.get("name") or key)))
        # Ordenar pelo label
        discovered.sort(key=lambda x: x[1])
        return discovered

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """Inicializa o form unificando configurações de módulos e ajustes numéricos."""
        # Capturar contexto de edição (usado em validações de unicidade)
        self._editing_tenant_pk = kwargs.pop("editing_tenant_pk", None)
        super().__init__(*args, **kwargs)

        dynamic_choices = self._build_dynamic_choices()
        self.fields["enabled_modules"].choices = dynamic_choices

        self.module_catalog = self._build_module_catalog(dynamic_choices)

        self._apply_field_help()

    def _build_dynamic_choices(self) -> list[tuple[str, str]]:
        """Monta as choices para enabled_modules, com fallback robusto."""
        dynamic_choices = self.discover_internal_modules() or []
        if not dynamic_choices:
            dynamic_choices = []
            for k, v in self.AVAILABLE_MODULES.items():
                label = str(v.get("name") or k)
                dynamic_choices.append((k, label))
            dynamic_choices.sort(key=lambda x: x[1])
        return dynamic_choices

    def _build_module_catalog(
        self,
        dynamic_choices: list[tuple[str, str]],
    ) -> list[tuple[str, list[dict[str, object]]]]:
        """Agrupa módulos por categoria e ordena para exibição no template."""
        catalog: dict[str, list[dict[str, object]]] = {}
        for key, label in dynamic_choices:
            meta = self.AVAILABLE_MODULES.get(key, {})
            icon_cfg = self.MODULE_ICONS_AND_COLORS.get(key, {})
            category_str = str(meta.get("category") or icon_cfg.get("category") or "Outros")
            if category_str not in catalog:
                catalog[category_str] = []
            catalog[category_str].append(
                {
                    "key": key,
                    "label": label,
                    "description": meta.get("description", ""),
                    "premium": bool(meta.get("premium")),
                    "icon": icon_cfg.get("icon", "fas fa-puzzle-piece"),
                    "color": icon_cfg.get("color", "text-muted"),
                },
            )
        for modules in catalog.values():
            modules.sort(key=lambda m: str(m.get("label") or ""))
        ordered: list[tuple[str, list[dict[str, object]]]] = []
        if "Gestão Básica" in catalog:
            ordered.append(("Gestão Básica", catalog.pop("Gestão Básica")))
        ordered.extend((cat, catalog[cat]) for cat in sorted(catalog))
        return ordered

    def _apply_field_help(self) -> None:
        """Ajusta labels e help_text, além de atributos de widgets numéricos."""
        if "portal_ativo" in self.fields:
            self.fields["portal_ativo"].label = "Acesso Externo (Portal) Ativo?"
            self.fields["portal_ativo"].help_text = (
                "Publica o portal externo para clientes/usuários finais. "
                'Requer o módulo "Portal do Cliente" habilitado na seção de Módulos.'
            )
        if "max_usuarios" in self.fields:
            self.fields["max_usuarios"].help_text = self.fields["max_usuarios"].help_text or "Use 0 para ilimitado."
            self.fields["max_usuarios"].widget.attrs["min"] = "0"
            self.fields["max_usuarios"].widget.attrs.setdefault("step", "1")
        if "max_armazenamento_gb" in self.fields:
            self.fields["max_armazenamento_gb"].help_text = (
                self.fields["max_armazenamento_gb"].help_text or "Use 0 para ilimitado."
            )
            self.fields["max_armazenamento_gb"].widget.attrs["min"] = "0"
            self.fields["max_armazenamento_gb"].widget.attrs.setdefault("step", "1")

    class Meta:
        """Metadados dos campos e widgets do formulário de configurações."""

        model = Tenant
        fields: ClassVar[list[str]] = [
            "subdomain",
            "logo",
            "codigo_interno",
            "status",
            "plano_assinatura",
            "data_ativacao_plano",
            "data_fim_trial",
            "max_usuarios",
            "max_armazenamento_gb",
            "data_proxima_cobranca",
            "portal_ativo",
            "timezone",
            "idioma_padrao",
            "moeda_padrao",
        ]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "subdomain": forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "meusubdominio"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control wizard-field", "accept": "image/*"}),
            "codigo_interno": forms.TextInput(
                attrs={"class": "form-control wizard-field", "placeholder": "Código de identificação interna"},
            ),
            "status": forms.Select(attrs={"class": "form-select wizard-field"}),
            "plano_assinatura": forms.Select(attrs={"class": "form-select wizard-field"}),
            "data_ativacao_plano": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "data_fim_trial": forms.DateTimeInput(
                attrs={"class": "form-control wizard-field", "type": "datetime-local"},
            ),
            "max_usuarios": forms.NumberInput(
                attrs={"class": "form-control wizard-field", "min": "1", "max": "1000", "placeholder": "5"},
            ),
            "max_armazenamento_gb": forms.NumberInput(
                attrs={"class": "form-control wizard-field", "min": "1", "max": "1000", "placeholder": "1"},
            ),
            "data_proxima_cobranca": forms.DateInput(attrs={"class": "form-control wizard-field", "type": "date"}),
            "portal_ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "timezone": forms.Select(attrs={"class": "form-select wizard-field"}),
            "idioma_padrao": forms.Select(attrs={"class": "form-select wizard-field"}),
            "moeda_padrao": forms.Select(attrs={"class": "form-select wizard-field"}),
        }

    def clean_logo(self) -> UploadedFile | None:
        """Valida tamanho e tipo do logo enviado."""
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo
        # Limite padrão 2MB (pode ser sobrescrito por settings)
        max_mb = getattr(settings, "TENANT_LOGO_MAX_SIZE_MB", 2)
        max_bytes = max_mb * 1024 * 1024
        size = getattr(logo, "size", None)
        if size and size > max_bytes:
            raise forms.ValidationError(_("O logo excede %sMB.") % max_mb)
        content_type = getattr(logo, "content_type", None)
        allowed = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/gif"}
        if content_type and content_type.lower() not in allowed:
            raise forms.ValidationError(_("Formato de imagem inválido. Use PNG, JPG, SVG ou GIF."))
        return logo

    def clean_max_usuarios(self) -> int | None:
        """Garante que o valor seja >= 0 (0 = ilimitado)."""
        val = self.cleaned_data.get("max_usuarios")
        if val is None:
            return val
        if val < 0:
            raise forms.ValidationError(_("Informe um número maior ou igual a 0 (0 = ilimitado)."))
        return val

    def clean_max_armazenamento_gb(self) -> int | None:
        """Garante que o valor seja >= 0 (0 = ilimitado)."""
        val = self.cleaned_data.get("max_armazenamento_gb")
        if val is None:
            return val
        if val < 0:
            raise forms.ValidationError(_("Informe um número maior ou igual a 0 (0 = ilimitado)."))
        return val

    def clean(self) -> dict[str, Any]:
        """Validações combinadas: dependências de portal_ativo e coerência de datas."""
        cleaned = super().clean()

        # 1) Dependência portal_ativo -> portal_cliente habilitado
        enabled = set(cleaned.get("enabled_modules") or [])
        if cleaned.get("portal_ativo") and "portal_cliente" not in enabled:
            cleaned["portal_ativo"] = False
            self.add_error(
                "portal_ativo",
                'Para ativar o acesso externo habilite também o módulo "Portal do Cliente" acima.',
            )

        # 2) Regras de datas
        ativ = cleaned.get("data_ativacao_plano")
        trial_end = cleaned.get("data_fim_trial")
        prox = cleaned.get("data_proxima_cobranca")
        today = timezone.localdate()

        def to_date(d: datetime | date) -> date:  # Normalizador seguro
            if isinstance(d, datetime):
                return d.date()
            return d

        ativ_d = to_date(ativ) if ativ else None
        trial_d = to_date(trial_end) if trial_end else None
        prox_d = to_date(prox) if prox else None

        if trial_d and ativ_d and trial_d < ativ_d:
            self.add_error("data_fim_trial", _("O fim do teste deve ser igual ou posterior à data de ativação."))
        if prox_d:
            if prox_d < today:
                self.add_error(
                    "data_proxima_cobranca",
                    _("A próxima cobrança não pode ser no passado."),
                )
            if ativ_d and prox_d < ativ_d:
                self.add_error(
                    "data_proxima_cobranca",
                    _("A próxima cobrança deve ser igual ou posterior à ativação."),
                )
        return cleaned

    def clean_subdomain(self) -> str | None:
        """Normaliza e valida unicidade e formato do subdomínio."""
        subdomain = self.cleaned_data.get("subdomain")
        if subdomain:
            subdomain = normalize_subdomain(subdomain)
            if not SUBDOMAIN_REGEX.match(subdomain):
                raise forms.ValidationError(
                    _("Subdomínio inválido. Use apenas letras minúsculas, números e hífen (não no início/fim)."),
                )
            if subdomain in RESERVED_SUBDOMAINS:
                raise forms.ValidationError(_("Este subdomínio é reservado. Escolha outro."))
            qs = Tenant.objects.filter(subdomain=subdomain)
            if hasattr(self, "_editing_tenant_pk") and self._editing_tenant_pk:
                qs = qs.exclude(pk=self._editing_tenant_pk)
            elif self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(_("Este subdomínio já está em uso."))
        return subdomain


class TenantAdminsWizardForm(forms.Form):
    """STEP 6: Administradores Iniciais (Opcional)."""

    admin_nome = forms.CharField(
        max_length=150,
        required=False,
        label=_("Nome do Administrador"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "Nome completo"}),
    )

    admin_email = forms.EmailField(
        required=False,
        label=_("E-mail do Administrador"),
        widget=forms.EmailInput(attrs={"class": "form-control wizard-field", "placeholder": "admin@empresa.com"}),
    )

    admin_usuario = forms.CharField(
        max_length=150,
        required=False,
        label=_("Nome de Usuário"),
        widget=forms.TextInput(attrs={"class": "form-control wizard-field", "placeholder": "usuario"}),
    )

    admin_senha = forms.CharField(
        max_length=128,
        required=False,
        label=_("Senha"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control wizard-field", "placeholder": "Digite uma senha segura"},
        ),
    )

    admin_confirmar_senha = forms.CharField(
        max_length=128,
        required=False,
        label=_("Confirmar Senha"),
        widget=forms.PasswordInput(attrs={"class": "form-control wizard-field", "placeholder": "Confirme a senha"}),
    )

    admin_telefone = forms.CharField(
        max_length=20,
        required=False,
        label=_("Telefone"),
        widget=forms.TextInput(
            attrs={"class": "form-control wizard-field phone-mask", "placeholder": "(11) 99999-9999"},
        ),
    )

    def clean(self) -> dict[str, Any]:
        """Valida senha e confirmação quando ambos presentes."""
        cleaned_data = super().clean()
        senha = cleaned_data.get("admin_senha")
        confirmar = cleaned_data.get("admin_confirmar_senha")

        if senha and confirmar and senha != confirmar:
            self.add_error("admin_confirmar_senha", _("As senhas não coincidem."))

        return cleaned_data


class TenantReviewWizardForm(forms.ModelForm):
    """STEP 7: Revisão & Confirmação."""

    confirmar_dados = forms.BooleanField(
        required=True,
        label=_("Confirmo que todos os dados estão corretos"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    aceitar_termos = forms.BooleanField(
        required=True,
        label=_("Li e aceito os Termos de Uso e Política de Privacidade"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    aceitar_comunicacoes = forms.BooleanField(
        required=False,
        label=_("Aceito receber comunicações sobre atualizações e novidades"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        """Configurações de campos e widgets do formulário de revisão."""

        model = Tenant
        fields: ClassVar[list[str]] = ["observacoes"]
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "observacoes": forms.Textarea(
                attrs={
                    "class": "form-control wizard-field",
                    "rows": 4,
                    "placeholder": "Observações sobre a empresa...",
                },
            ),
        }

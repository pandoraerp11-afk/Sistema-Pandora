# obras/forms.py
from django import forms
from django.core.exceptions import ValidationError

from clientes.models import Cliente
from core.forms import BasePandoraForm
from core.utils import get_current_tenant

from .models import DocumentoObra, ModeloUnidade, Obra, Unidade


class ObraForm(BasePandoraForm):
    """Formulário para criar e editar uma Obra"""

    class Meta:
        model = Obra
        fields = [
            "nome",
            "tipo_obra",
            "cno",
            "cliente",
            "endereco",
            "cidade",
            "estado",
            "cep",
            "data_inicio",
            "data_previsao_termino",
            "data_termino",
            "valor_contrato",
            "valor_total",
            "status",
            "progresso",
            "observacoes",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome da obra"}),
            "tipo_obra": forms.Select(attrs={"class": "form-control"}),
            "cno": forms.TextInput(attrs={"class": "form-control", "placeholder": "Cadastro Nacional de Obras"}),
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "endereco": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Endereço completo da obra"}
            ),
            "cidade": forms.TextInput(attrs={"class": "form-control", "placeholder": "Cidade"}),
            "estado": forms.TextInput(attrs={"class": "form-control", "placeholder": "Estado"}),
            "cep": forms.TextInput(attrs={"class": "form-control", "placeholder": "00000-000"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_previsao_termino": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_termino": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valor_contrato": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}),
            "valor_total": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "progresso": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "100", "placeholder": "Progresso em %"}
            ),
            "observacoes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Observações adicionais sobre a obra"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset para clientes
        cliente_qs = Cliente.objects.all()
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant and hasattr(Cliente, "tenant"):
                cliente_qs = cliente_qs.filter(tenant=tenant)

        self.fields["cliente"].queryset = cliente_qs
        self.fields["cliente"].empty_label = "Selecione um cliente (opcional)"

        # Tornar alguns campos obrigatórios
        self.fields["nome"].required = True
        self.fields["endereco"].required = True
        self.fields["cidade"].required = True
        self.fields["estado"].required = True
        self.fields["data_inicio"].required = True
        self.fields["valor_contrato"].required = True

    def clean_cno(self):
        """Validar CNO único"""
        cno = self.cleaned_data.get("cno")
        if cno:
            qs = Obra.objects.filter(cno=cno)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Já existe uma obra com este CNO.")
        return cno

    def clean(self):
        """Validações gerais do formulário"""
        cleaned_data = super().clean()
        data_inicio = cleaned_data.get("data_inicio")
        data_previsao_termino = cleaned_data.get("data_previsao_termino")
        data_termino = cleaned_data.get("data_termino")
        valor_contrato = cleaned_data.get("valor_contrato")
        valor_total = cleaned_data.get("valor_total")
        progresso = cleaned_data.get("progresso")

        # Validar datas
        if data_inicio and data_previsao_termino and data_inicio > data_previsao_termino:
            raise ValidationError("A data de início não pode ser posterior à data de previsão de término.")

        if data_inicio and data_termino and data_inicio > data_termino:
            raise ValidationError("A data de início não pode ser posterior à data de término.")

        # Validar valores
        if valor_contrato and valor_contrato < 0:
            raise ValidationError("O valor do contrato não pode ser negativo.")

        if valor_total and valor_total < 0:
            raise ValidationError("O valor total não pode ser negativo.")

        # Validar progresso
        if progresso is not None and (progresso < 0 or progresso > 100):
            raise ValidationError("O progresso deve estar entre 0 e 100%.")

        return cleaned_data


class UnidadeForm(BasePandoraForm):
    """Formulário para Unidades da obra"""

    class Meta:
        model = Unidade
        fields = ["identificador", "tipo_unidade", "area_m2", "cliente", "status", "modelo", "bloco", "andar", "numero"]
        widgets = {
            "identificador": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: Apto 101, Casa 5, etc."}
            ),
            "tipo_unidade": forms.Select(attrs={"class": "form-control"}),
            "area_m2": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Área em m²"}),
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "modelo": forms.Select(attrs={"class": "form-control select2"}),
            "bloco": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Torre A"}),
            "andar": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ex.: 1, 2, 3..."}),
            "numero": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: 101, 202"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset para clientes
        cliente_qs = Cliente.objects.all()
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant and hasattr(Cliente, "tenant"):
                cliente_qs = cliente_qs.filter(tenant=tenant)

        self.fields["cliente"].queryset = cliente_qs
        self.fields["cliente"].empty_label = "Nenhum cliente (Unidade disponível)"
        self.fields["identificador"].required = True
        # Se a instância tiver obra, restringe modelos à mesma obra
        if hasattr(self.instance, "obra") and self.instance.obra_id:
            self.fields["modelo"].queryset = ModeloUnidade.objects.filter(obra=self.instance.obra)
        else:
            self.fields["modelo"].queryset = ModeloUnidade.objects.none()

    def clean_identificador(self):
        """Validar identificador único por obra"""
        identificador = self.cleaned_data.get("identificador")
        if identificador and hasattr(self, "obra"):
            qs = Unidade.objects.filter(obra=self.obra, identificador=identificador)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Já existe uma unidade com este identificador nesta obra.")
        return identificador


class ModeloUnidadeForm(BasePandoraForm):
    class Meta:
        model = ModeloUnidade
        fields = [
            "obra",
            "codigo",
            "nome",
            "tipo_unidade",
            "dormitorios",
            "suites",
            "banheiros",
            "vagas",
            "area_privativa",
            "area_total",
            "preco_sugerido",
            "ambientes",
        ]
        widgets = {
            "obra": forms.HiddenInput(),
            "codigo": forms.TextInput(attrs={"class": "form-control", "placeholder": "01, 02, 03..."}),
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apto Tipo 01"}),
            "tipo_unidade": forms.Select(attrs={"class": "form-control"}),
            "dormitorios": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "suites": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "banheiros": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "vagas": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "area_privativa": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "area_total": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "preco_sugerido": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "ambientes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "JSON com ambientes"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Permitir deixar o código em branco para auto-geração
        if "codigo" in self.fields:
            self.fields["codigo"].required = False


class GerarUnidadesEmMassaForm(forms.Form):
    """Gera unidades automaticamente: intervalo de andares e numeração por modelo."""

    bloco = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Torre A"})
    )
    andar_inicial = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control"}))
    andar_final = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control"}))
    prefixo_numero = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: 1 para 101, 102"})
    )
    numeros_por_andar = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: 01,02,03,04"})
    )
    modelo = forms.ModelChoiceField(
        queryset=ModeloUnidade.objects.all(), widget=forms.Select(attrs={"class": "form-control select2"})
    )

    def __init__(self, *args, **kwargs):
        self.obra = kwargs.pop("obra", None)
        super().__init__(*args, **kwargs)
        if self.obra:
            self.fields["modelo"].queryset = ModeloUnidade.objects.filter(obra=self.obra)
        # aplicar classes padrão aos widgets (similar ao BasePandoraForm)
        for field in self.fields.values():
            w = field.widget
            cls = w.attrs.get("class", "")
            if not isinstance(w, (forms.CheckboxInput, forms.FileInput, forms.RadioSelect)):
                if "form-control" not in cls:
                    w.attrs["class"] = f"{cls} form-control".strip()
            if isinstance(w, forms.Select) and "select2" not in w.attrs.get("class", ""):
                w.attrs["class"] = f"{w.attrs.get('class', '')} select2".strip()

    def clean(self):
        cleaned = super().clean()
        ai = cleaned.get("andar_inicial")
        af = cleaned.get("andar_final")
        if ai is not None and af is not None and ai > af:
            raise ValidationError("Andar inicial não pode ser maior que o final.")
        return cleaned


class DocumentoObraForm(BasePandoraForm):
    """Formulário para Documentos da obra"""

    class Meta:
        model = DocumentoObra
        fields = ["descricao", "categoria", "arquivo"]
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Descrição do documento"}),
            "categoria": forms.Select(attrs={"class": "form-control"}),
            "arquivo": forms.FileInput(
                attrs={"class": "form-control-file", "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.xls,.xlsx"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descricao"].required = True
        self.fields["arquivo"].required = True

    def clean_arquivo(self):
        """Validar arquivo enviado"""
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo:
            # Validar tamanho do arquivo (máximo 10MB)
            if arquivo.size > 10 * 1024 * 1024:
                raise ValidationError("O arquivo não pode ser maior que 10MB.")

            # Validar extensão do arquivo
            nome_arquivo = arquivo.name.lower()
            extensoes_permitidas = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xls", ".xlsx"]
            if not any(nome_arquivo.endswith(ext) for ext in extensoes_permitidas):
                raise ValidationError("Tipo de arquivo não permitido. Use: PDF, DOC, DOCX, JPG, PNG, XLS ou XLSX.")

        return arquivo


# Formulário de busca avançada
class ObraBuscaForm(forms.Form):
    """Formulário para busca avançada de obras"""

    nome = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome da obra"})
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        empty_label="Todos os clientes",
        widget=forms.Select(attrs={"class": "form-control select2"}),
    )
    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + Obra.STATUS_CHOICES if hasattr(Obra, "STATUS_CHOICES") else [("", "Todos")],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    data_inicio_de = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date", "placeholder": "Data início de"}),
    )
    data_inicio_ate = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date", "placeholder": "Data início até"}),
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Configurar queryset para clientes
        if self.request:
            tenant = get_current_tenant(self.request)
            if tenant and hasattr(Cliente, "tenant"):
                self.fields["cliente"].queryset = Cliente.objects.filter(tenant=tenant)

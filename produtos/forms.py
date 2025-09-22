# produtos/forms.py

import pandas as pd
from django import forms
from django.core.exceptions import ValidationError

from cadastros_gerais.forms import BasePandoraForm

from .models import Categoria, Produto, ProdutoDocumento, ProdutoImagem, ProdutoVariacao


class CategoriaForm(BasePandoraForm):
    """Formulário para categorias de produtos"""

    class Meta:
        model = Categoria
        fields = ["nome", "descricao", "ativo"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome da categoria", "maxlength": 100}
            ),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descrição detalhada da categoria"}
            ),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_nome(self):
        """Validação customizada para o nome da categoria"""
        nome = self.cleaned_data.get("nome")
        if nome:
            nome = nome.strip().title()

            # Verificar duplicação
            if self.instance.pk:
                if Categoria.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
                    raise ValidationError("Já existe uma categoria com este nome.")
            elif Categoria.objects.filter(nome__iexact=nome).exists():
                raise ValidationError("Já existe uma categoria com este nome.")

        return nome

    def clean_descricao(self):
        """Validação para descrição"""
        descricao = self.cleaned_data.get("descricao")
        if descricao:
            descricao = descricao.strip()
            if len(descricao) < 10:
                raise ValidationError("A descrição deve ter pelo menos 10 caracteres.")
        return descricao


class ProdutoForm(BasePandoraForm):
    """Formulário principal para produtos com validações avançadas"""

    class Meta:
        model = Produto
        fields = [
            "nome",
            "codigo_barras",
            "categoria",
            "descricao",
            "especificacoes_tecnicas",
            "unidade",
            "preco_unitario",
            "preco_custo",
            "tipo_custo",
            "margem_lucro",
            "estoque_atual",
            "estoque_minimo",
            "estoque_maximo",
            "peso",
            "altura",
            "largura",
            "profundidade",
            "fabricante",
            "marca",
            "modelo",
            "garantia",
            "ncm",
            "ativo",
            "destaque",
            "controla_estoque",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome do produto", "required": True}
            ),
            "codigo_barras": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Código de barras (opcional)"}
            ),
            "categoria": forms.Select(attrs={"class": "form-select", "required": True}),
            "ncm": forms.TextInput(attrs={"class": "form-control", "placeholder": "NCM (opcional)", "maxlength": 10}),
            "descricao": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Descrição do produto"}
            ),
            "especificacoes_tecnicas": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Especificações técnicas detalhadas"}
            ),
            "unidade": forms.Select(attrs={"class": "form-select"}),
            "preco_unitario": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "preco_custo": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "tipo_custo": forms.Select(attrs={"class": "form-select"}),
            "margem_lucro": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100", "placeholder": "0,00"}
            ),
            "estoque_atual": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "0"}),
            "estoque_minimo": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "0"}),
            "estoque_maximo": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "0"}),
            "peso": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.001", "min": "0", "placeholder": "0,000"}
            ),
            "altura": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "largura": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "profundidade": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "0,00"}
            ),
            "fabricante": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do fabricante"}),
            "marca": forms.TextInput(attrs={"class": "form-control", "placeholder": "Marca do produto"}),
            "modelo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Modelo do produto"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "destaque": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "controla_estoque": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "garantia": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 12 meses"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configurar choices dinâmicos
        if "categoria" in self.fields:
            self.fields["categoria"].queryset = Categoria.objects.filter(ativo=True).order_by("nome")
            self.fields["categoria"].empty_label = "Selecione uma categoria"

    def clean_codigo(self):
        """Validação para código único"""
        codigo = self.cleaned_data.get("codigo")
        if codigo:
            codigo = codigo.strip().upper()

            # Verificar duplicação
            if self.instance.pk:
                if Produto.objects.filter(codigo=codigo).exclude(pk=self.instance.pk).exists():
                    raise ValidationError("Já existe um produto com este código.")
            elif Produto.objects.filter(codigo=codigo).exists():
                raise ValidationError("Já existe um produto com este código.")

        return codigo

    def clean_codigo_barras(self):
        """Validação para código de barras único"""
        codigo_barras = self.cleaned_data.get("codigo_barras")
        if codigo_barras:
            codigo_barras = codigo_barras.strip()

            # Verificar duplicação
            if self.instance.pk:
                if Produto.objects.filter(codigo_barras=codigo_barras).exclude(pk=self.instance.pk).exists():
                    raise ValidationError("Já existe um produto com este código de barras.")
            elif Produto.objects.filter(codigo_barras=codigo_barras).exists():
                raise ValidationError("Já existe um produto com este código de barras.")

        return codigo_barras

    def clean_preco_unitario(self):
        """Validação para preço unitário"""
        preco = self.cleaned_data.get("preco_unitario")
        if preco is not None and preco <= 0:
            raise ValidationError("O preço unitário deve ser maior que zero.")
        return preco

    def clean_preco_custo(self):
        """Validação para preço de custo"""
        preco_custo = self.cleaned_data.get("preco_custo")
        if preco_custo is not None and preco_custo < 0:
            raise ValidationError("O preço de custo não pode ser negativo.")
        return preco_custo

    def clean_margem_lucro(self):
        """Validação para margem de lucro"""
        margem = self.cleaned_data.get("margem_lucro")
        if margem is not None and (margem < 0 or margem > 1000):
            raise ValidationError("A margem de lucro deve estar entre 0% e 1000%.")
        return margem

    def clean(self):
        """Validações que dependem de múltiplos campos"""
        cleaned_data = super().clean()
        cleaned_data.get("estoque_atual")
        estoque_minimo = cleaned_data.get("estoque_minimo")
        estoque_maximo = cleaned_data.get("estoque_maximo")
        preco_unitario = cleaned_data.get("preco_unitario")
        preco_custo = cleaned_data.get("preco_custo")
        margem_lucro = cleaned_data.get("margem_lucro")

        # Validar estoque
        if estoque_minimo is not None and estoque_maximo is not None and estoque_minimo > estoque_maximo:
            raise ValidationError("O estoque mínimo não pode ser maior que o estoque máximo.")

        # Validar preços e margem
        if preco_unitario and preco_custo and margem_lucro:
            # Calcular margem baseada nos preços
            margem_calculada = ((preco_unitario - preco_custo) / preco_custo) * 100 if preco_custo > 0 else 0

            # Permitir diferença de até 5% entre margem informada e calculada
            if abs(margem_calculada - margem_lucro) > 5:
                self.add_error(
                    "margem_lucro", f"A margem de lucro calculada ({margem_calculada:.2f}%) difere muito da informada."
                )

        return cleaned_data


class ProdutoBuscaForm(forms.Form):
    """Formulário para busca e filtros de produtos"""

    busca = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Buscar por nome, código ou descrição...",
                "autocomplete": "off",
            }
        ),
    )

    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.filter(ativo=True).order_by("nome"),
        required=False,
        empty_label="Todas as categorias",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    ativo = forms.ChoiceField(
        choices=[("", "Todos"), ("1", "Ativos"), ("0", "Inativos")],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    estoque = forms.ChoiceField(
        choices=[
            ("", "Qualquer estoque"),
            ("baixo", "Estoque baixo"),
            ("zerado", "Sem estoque"),
            ("alto", "Estoque alto"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    destaque = forms.ChoiceField(
        choices=[("", "Todos"), ("1", "Em destaque")],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    preco_min = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Preço mínimo", "step": "0.01"}),
    )

    preco_max = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Preço máximo", "step": "0.01"}),
    )

    ordenar = forms.ChoiceField(
        choices=[
            ("", "Mais recentes"),
            ("nome", "Nome A-Z"),
            ("preco_asc", "Menor preço"),
            ("preco_desc", "Maior preço"),
            ("estoque", "Menor estoque"),
            ("categoria", "Categoria"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ProdutoFiltroForm(forms.Form):
    """Formulário avançado para filtros de produtos"""

    # Campos básicos
    nome = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    codigo = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(), required=False, widget=forms.Select(attrs={"class": "form-select"})
    )

    # Filtros de preço
    preco_min = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={"class": "form-control"}))
    preco_max = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={"class": "form-control"}))

    # Filtros de estoque
    estoque_min = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={"class": "form-control"}))
    estoque_max = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={"class": "form-control"}))

    # Status
    ativo = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    destaque = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


class ProdutoImagemForm(BasePandoraForm):
    """Formulário para imagens de produtos"""

    class Meta:
        model = ProdutoImagem
        fields = ["imagem", "titulo", "ordem"]
        widgets = {
            "imagem": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Título da imagem (opcional)"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "0"}),
        }

    def clean_imagem(self):
        """Validação para imagem"""
        imagem = self.cleaned_data.get("imagem")
        if imagem:
            # Verificar tamanho (máximo 5MB)
            if imagem.size > 5 * 1024 * 1024:
                raise ValidationError("A imagem deve ter no máximo 5MB.")

            # Verificar tipo
            if not imagem.content_type.startswith("image/"):
                raise ValidationError("O arquivo deve ser uma imagem.")

        return imagem


class ProdutoVariacaoForm(BasePandoraForm):
    """Formulário para variações de produtos"""

    class Meta:
        model = ProdutoVariacao
        fields = ["nome", "descricao", "preco_adicional", "estoque", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome da variação"}),
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Descrição da variação"}),
            "preco_adicional": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}
            ),
            "estoque": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "0"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProdutoDocumentoForm(BasePandoraForm):
    """Formulário para documentos de produtos"""

    class Meta:
        model = ProdutoDocumento
        fields = ["titulo", "arquivo", "tipo"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Título do documento"}),
            "arquivo": forms.FileInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_arquivo(self):
        """Validação para arquivo"""
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo:
            # Verificar tamanho (máximo 10MB)
            if arquivo.size > 10 * 1024 * 1024:
                raise ValidationError("O arquivo deve ter no máximo 10MB.")

        return arquivo


class ProdutoImportForm(forms.Form):
    """Formulário para importação de produtos"""

    arquivo = forms.FileField(
        label="Arquivo de importação",
        help_text="Formatos aceitos: CSV, Excel (.xlsx, .xls)",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv,.xlsx,.xls"}),
    )

    sobrescrever = forms.BooleanField(
        label="Sobrescrever produtos existentes",
        help_text="Se marcado, produtos com mesmo código serão atualizados",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    criar_categorias = forms.BooleanField(
        label="Criar categorias automaticamente",
        help_text="Se marcado, categorias que não existem serão criadas",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_arquivo(self):
        """Validação para arquivo de importação"""
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo:
            # Verificar extensão
            nome = arquivo.name.lower()
            if not (nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls")):
                raise ValidationError("Formato de arquivo não suportado. Use CSV ou Excel.")

            # Verificar tamanho (máximo 50MB)
            if arquivo.size > 50 * 1024 * 1024:
                raise ValidationError("O arquivo deve ter no máximo 50MB.")

            # Tentar ler o arquivo para validar estrutura
            try:
                df = pd.read_csv(arquivo, nrows=1) if nome.endswith(".csv") else pd.read_excel(arquivo, nrows=1)

                # Verificar colunas obrigatórias
                colunas_obrigatorias = ["Nome"]
                for coluna in colunas_obrigatorias:
                    if coluna not in df.columns:
                        raise ValidationError(f'Coluna obrigatória "{coluna}" não encontrada no arquivo.')

                # Resetar posição do arquivo
                arquivo.seek(0)

            except Exception as e:
                if isinstance(e, ValidationError):
                    raise
                raise ValidationError(f"Erro ao ler arquivo: {str(e)}")

        return arquivo


class ProdutoExportForm(forms.Form):
    """Formulário para exportação de produtos"""

    formato = forms.ChoiceField(
        choices=[("csv", "CSV"), ("excel", "Excel")],
        initial="excel",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    incluir_inativos = forms.BooleanField(
        label="Incluir produtos inativos",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    incluir_estoque = forms.BooleanField(
        label="Incluir informações de estoque",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    incluir_precos = forms.BooleanField(
        label="Incluir informações de preços",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

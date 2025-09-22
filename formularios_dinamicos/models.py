import uuid

from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


class TipoCampo(models.TextChoices):
    TEXT = "text", "Texto"
    TEXTAREA = "textarea", "Área de Texto"
    EMAIL = "email", "E-mail"
    NUMBER = "number", "Número"
    DATE = "date", "Data"
    DATETIME = "datetime", "Data e Hora"
    TIME = "time", "Hora"
    SELECT = "select", "Lista de Seleção"
    RADIO = "radio", "Botões de Rádio"
    CHECKBOX = "checkbox", "Caixas de Seleção"
    FILE = "file", "Arquivo"
    IMAGE = "image", "Imagem"
    URL = "url", "URL"
    PHONE = "phone", "Telefone"
    CPF = "cpf", "CPF"
    CNPJ = "cnpj", "CNPJ"
    CEP = "cep", "CEP"
    CURRENCY = "currency", "Moeda"
    PERCENTAGE = "percentage", "Porcentagem"
    RATING = "rating", "Avaliação (Estrelas)"
    COLOR = "color", "Cor"
    RANGE = "range", "Intervalo"
    HIDDEN = "hidden", "Campo Oculto"


class StatusFormulario(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    ATIVO = "ativo", "Ativo"
    INATIVO = "inativo", "Inativo"
    ARQUIVADO = "arquivado", "Arquivado"


class StatusResposta(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    ENVIADO = "enviado", "Enviado"
    EM_ANALISE = "em_analise", "Em Análise"
    APROVADO = "aprovado", "Aprovado"
    REJEITADO = "rejeitado", "Rejeitado"
    ARQUIVADO = "arquivado", "Arquivado"


class FormularioDinamico(models.Model):
    """Modelo principal para formulários dinâmicos"""

    # Identificação
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="Slug")

    # Status e configurações
    status = models.CharField(
        max_length=20, choices=StatusFormulario.choices, default=StatusFormulario.RASCUNHO, verbose_name="Status"
    )
    publico = models.BooleanField(default=False, verbose_name="Público")
    permite_multiplas_respostas = models.BooleanField(default=False, verbose_name="Permite Múltiplas Respostas")
    requer_login = models.BooleanField(default=True, verbose_name="Requer Login")

    # Datas
    data_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Data de Início")
    data_fim = models.DateTimeField(null=True, blank=True, verbose_name="Data de Fim")

    # Configurações de notificação
    notificar_nova_resposta = models.BooleanField(default=True, verbose_name="Notificar Nova Resposta")
    emails_notificacao = models.TextField(
        blank=True, verbose_name="E-mails para Notificação", help_text="Um e-mail por linha"
    )

    # Configurações de aparência
    cor_tema = models.CharField(
        max_length=7, default="#007bff", validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")], verbose_name="Cor do Tema"
    )
    css_personalizado = models.TextField(blank=True, verbose_name="CSS Personalizado")

    # Configurações avançadas
    configuracoes_avancadas = models.JSONField(default=dict, blank=True, verbose_name="Configurações Avançadas")

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="formularios_criados")

    class Meta:
        verbose_name = "Formulário Dinâmico"
        verbose_name_plural = "Formulários Dinâmicos"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo

    @property
    def esta_ativo(self):
        """Verifica se o formulário está ativo e dentro do período"""
        if self.status != StatusFormulario.ATIVO:
            return False

        agora = timezone.now()

        if self.data_inicio and agora < self.data_inicio:
            return False

        return not (self.data_fim and agora > self.data_fim)

    @property
    def total_respostas(self):
        """Retorna o total de respostas do formulário"""
        return self.respostas.count()

    @property
    def total_campos(self):
        """Retorna o total de campos do formulário"""
        return self.campos.count()


class CampoFormulario(models.Model):
    """Campos dos formulários dinâmicos"""

    formulario = models.ForeignKey(FormularioDinamico, on_delete=models.CASCADE, related_name="campos")

    # Identificação
    nome = models.CharField(max_length=100, verbose_name="Nome do Campo")
    label = models.CharField(max_length=200, verbose_name="Rótulo")
    tipo = models.CharField(max_length=20, choices=TipoCampo.choices, verbose_name="Tipo do Campo")

    # Configurações
    obrigatorio = models.BooleanField(default=False, verbose_name="Obrigatório")
    placeholder = models.CharField(max_length=200, blank=True, verbose_name="Placeholder")
    help_text = models.CharField(max_length=500, blank=True, verbose_name="Texto de Ajuda")
    valor_padrao = models.TextField(blank=True, verbose_name="Valor Padrão")

    # Validações
    min_length = models.IntegerField(null=True, blank=True, verbose_name="Tamanho Mínimo")
    max_length = models.IntegerField(null=True, blank=True, verbose_name="Tamanho Máximo")
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Valor Mínimo")
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Valor Máximo")
    regex_validacao = models.CharField(max_length=500, blank=True, verbose_name="Regex de Validação")

    # Opções para campos de seleção
    opcoes = models.JSONField(
        default=list, blank=True, verbose_name="Opções", help_text="Para campos select, radio e checkbox"
    )

    # Configurações de aparência
    css_classes = models.CharField(max_length=200, blank=True, verbose_name="Classes CSS")
    largura_coluna = models.IntegerField(default=12, verbose_name="Largura da Coluna (1-12)")

    # Ordem e agrupamento
    ordem = models.IntegerField(default=0, verbose_name="Ordem")
    grupo = models.CharField(max_length=100, blank=True, verbose_name="Grupo")

    # Configurações avançadas
    configuracoes_avancadas = models.JSONField(default=dict, blank=True, verbose_name="Configurações Avançadas")

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campo do Formulário"
        verbose_name_plural = "Campos do Formulário"
        ordering = ["ordem", "criado_em"]
        unique_together = ["formulario", "nome"]

    def __str__(self):
        return f"{self.formulario.titulo} - {self.label}"

    def get_opcoes_list(self):
        """Retorna as opções como lista de dicionários"""
        if isinstance(self.opcoes, list):
            return self.opcoes
        return []

    def set_opcoes_from_text(self, texto):
        """Define opções a partir de texto (uma opção por linha)"""
        linhas = [linha.strip() for linha in texto.split("\n") if linha.strip()]
        self.opcoes = [{"value": linha, "label": linha} for linha in linhas]


class RespostaFormulario(models.Model):
    """Respostas aos formulários dinâmicos"""

    formulario = models.ForeignKey(FormularioDinamico, on_delete=models.CASCADE, related_name="respostas")
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="respostas_formularios"
    )

    # Identificação
    token = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="Token")

    # Status
    status = models.CharField(
        max_length=20, choices=StatusResposta.choices, default=StatusResposta.RASCUNHO, verbose_name="Status"
    )

    # Dados da resposta
    dados = models.JSONField(default=dict, verbose_name="Dados da Resposta")

    # Informações de submissão
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    # Análise e aprovação
    analisado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="respostas_analisadas"
    )
    analisado_em = models.DateTimeField(null=True, blank=True)
    observacoes_analise = models.TextField(blank=True, verbose_name="Observações da Análise")

    class Meta:
        verbose_name = "Resposta do Formulário"
        verbose_name_plural = "Respostas do Formulário"
        ordering = ["-criado_em"]

    def __str__(self):
        usuario_str = self.usuario.get_full_name() if self.usuario else "Anônimo"
        return f"{self.formulario.titulo} - {usuario_str} - {self.criado_em.strftime('%d/%m/%Y')}"

    def get_valor_campo(self, nome_campo):
        """Retorna o valor de um campo específico"""
        return self.dados.get(nome_campo)

    def set_valor_campo(self, nome_campo, valor):
        """Define o valor de um campo específico"""
        self.dados[nome_campo] = valor

    @property
    def pode_ser_editado(self):
        """Verifica se a resposta pode ser editada"""
        return self.status in [StatusResposta.RASCUNHO, StatusResposta.REJEITADO]


class ArquivoResposta(models.Model):
    """Arquivos anexados às respostas"""

    resposta = models.ForeignKey(RespostaFormulario, on_delete=models.CASCADE, related_name="arquivos")
    campo = models.CharField(max_length=100, verbose_name="Campo")

    # Arquivo
    arquivo = models.FileField(upload_to="formularios_dinamicos/arquivos/%Y/%m/")
    nome_original = models.CharField(max_length=255, verbose_name="Nome Original")
    tamanho = models.IntegerField(verbose_name="Tamanho (bytes)")
    tipo_mime = models.CharField(max_length=100, verbose_name="Tipo MIME")

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arquivo da Resposta"
        verbose_name_plural = "Arquivos das Respostas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.resposta} - {self.nome_original}"


class LogFormulario(models.Model):
    """Log de atividades dos formulários"""

    formulario = models.ForeignKey(FormularioDinamico, on_delete=models.CASCADE, related_name="logs")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Ação
    acao = models.CharField(max_length=100, verbose_name="Ação")
    descricao = models.TextField(verbose_name="Descrição")

    # Dados adicionais
    dados_anteriores = models.JSONField(default=dict, blank=True)
    dados_novos = models.JSONField(default=dict, blank=True)

    # Informações técnicas
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Metadados
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log do Formulário"
        verbose_name_plural = "Logs dos Formulários"
        ordering = ["-timestamp"]

    def __str__(self):
        usuario_str = self.usuario.get_full_name() if self.usuario else "Sistema"
        return f"{self.formulario.titulo} - {self.acao} - {usuario_str}"


class TemplateFormulario(models.Model):
    """Templates pré-definidos para formulários"""

    nome = models.CharField(max_length=200, verbose_name="Nome do Template")
    descricao = models.TextField(verbose_name="Descrição")
    categoria = models.CharField(max_length=100, verbose_name="Categoria")

    # Configuração do template
    configuracao = models.JSONField(verbose_name="Configuração do Template")

    # Status
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    publico = models.BooleanField(default=False, verbose_name="Público")

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Template de Formulário"
        verbose_name_plural = "Templates de Formulários"
        ordering = ["categoria", "nome"]

    def __str__(self):
        return f"{self.categoria} - {self.nome}"


class CondicaoFormulario(models.Model):
    """Condições para exibição de campos (lógica condicional)"""

    formulario = models.ForeignKey(FormularioDinamico, on_delete=models.CASCADE, related_name="condicoes")
    campo_origem = models.ForeignKey(CampoFormulario, on_delete=models.CASCADE, related_name="condicoes_origem")
    campo_destino = models.ForeignKey(CampoFormulario, on_delete=models.CASCADE, related_name="condicoes_destino")

    # Condição
    operador = models.CharField(
        max_length=20,
        choices=[
            ("equals", "Igual a"),
            ("not_equals", "Diferente de"),
            ("contains", "Contém"),
            ("not_contains", "Não contém"),
            ("greater_than", "Maior que"),
            ("less_than", "Menor que"),
            ("is_empty", "Está vazio"),
            ("is_not_empty", "Não está vazio"),
        ],
        verbose_name="Operador",
    )

    valor_comparacao = models.TextField(blank=True, verbose_name="Valor de Comparação")

    # Ação
    acao = models.CharField(
        max_length=20,
        choices=[
            ("show", "Mostrar"),
            ("hide", "Ocultar"),
            ("require", "Tornar obrigatório"),
            ("optional", "Tornar opcional"),
        ],
        verbose_name="Ação",
    )

    # Metadados
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Condição do Formulário"
        verbose_name_plural = "Condições do Formulário"
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.campo_origem.label} {self.operador} {self.valor_comparacao} → {self.acao} {self.campo_destino.label}"

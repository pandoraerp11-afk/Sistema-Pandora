# funcionarios/models_estoque.py
# EXTENSÕES DO MÓDULO FUNCIONÁRIOS PARA CONTROLE DE ESTOQUE
# Implementação da Fase 1 e 2 do Plano de Modernização

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import Funcionario


class PerfilFuncionario(models.Model):
    """Perfil específico para controle de materiais/estoque"""

    funcionario = models.OneToOneField(
        Funcionario, on_delete=models.CASCADE, related_name="perfil_estoque", verbose_name=_("Funcionário")
    )
    pode_retirar_materiais = models.BooleanField(
        default=False,
        verbose_name=_("Pode Retirar Materiais"),
        help_text=_("Define se o funcionário pode solicitar retirada de materiais"),
    )
    limite_valor_retirada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Limite de Valor para Retirada"),
        help_text=_("Limite máximo em R$ que o funcionário pode retirar sem aprovação especial"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    necessita_aprovacao = models.BooleanField(
        default=True,
        verbose_name=_("Necessita Aprovação"),
        help_text=_("Define se as solicitações precisam de aprovação"),
    )
    aprovador = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionarios_supervisionados",
        verbose_name=_("Aprovador Padrão"),
        help_text=_("Funcionário que aprova as solicitações deste funcionário"),
    )
    depositos_autorizados = models.ManyToManyField(
        "estoque.Deposito",
        blank=True,
        verbose_name=_("Depósitos Autorizados"),
        help_text=_("Depósitos dos quais o funcionário pode retirar materiais"),
    )
    categorias_autorizadas = models.ManyToManyField(
        "produtos.Categoria",
        blank=True,
        verbose_name=_("Categorias Autorizadas"),
        help_text=_("Categorias de produtos que o funcionário pode retirar"),
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Perfil de Funcionário para Estoque")
        verbose_name_plural = _("Perfis de Funcionários para Estoque")
        ordering = ["funcionario__nome_completo"]

    def __str__(self):
        return f"Perfil Estoque - {self.funcionario.nome_completo}"


class CrachaFuncionario(models.Model):
    """Controle de crachás para identificação rápida"""

    funcionario = models.OneToOneField(
        Funcionario, on_delete=models.CASCADE, related_name="cracha", verbose_name=_("Funcionário")
    )
    codigo_cracha = models.CharField(
        max_length=50, unique=True, verbose_name=_("Código do Crachá"), help_text=_("Código único impresso no crachá")
    )
    codigo_barras = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Código de Barras"),
        help_text=_("Código de barras para leitura automática"),
    )
    qr_code = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("QR Code"),
        help_text=_("QR Code para leitura via smartphone"),
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    data_emissao = models.DateField(auto_now_add=True, verbose_name=_("Data de Emissão"))
    data_validade = models.DateField(
        null=True, blank=True, verbose_name=_("Data de Validade"), help_text=_("Data de validade do crachá (opcional)")
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("Crachá de Funcionário")
        verbose_name_plural = _("Crachás de Funcionários")
        ordering = ["funcionario__nome_completo"]

    def __str__(self):
        return f"Crachá {self.codigo_cracha} - {self.funcionario.nome_completo}"


class SolicitacaoMaterial(models.Model):
    """Solicitação de materiais por funcionários"""

    STATUS_CHOICES = [
        ("RASCUNHO", _("Rascunho")),
        ("PENDENTE", _("Pendente")),
        ("EM_ANALISE", _("Em Análise")),
        ("APROVADA", _("Aprovada")),
        ("APROVADA_PARCIAL", _("Aprovada Parcialmente")),
        ("REJEITADA", _("Rejeitada")),
        ("ENTREGUE", _("Entregue")),
        ("ENTREGUE_PARCIAL", _("Parcialmente Entregue")),
        ("CANCELADA", _("Cancelada")),
        ("FINALIZADA", _("Finalizada")),
    ]

    TIPO_CHOICES = [
        ("OBRA", _("Para Obra")),
        ("MANUTENCAO", _("Manutenção")),
        ("EPI", _("EPI - Equipamento de Proteção Individual")),
        ("FERRAMENTAS", _("Ferramentas")),
        ("CONSUMO_GERAL", _("Consumo Geral")),
        ("REFORMA", _("Reforma")),
        ("EMERGENCIA", _("Emergência")),
    ]

    PRIORIDADE_CHOICES = [
        ("BAIXA", _("Baixa")),
        ("MEDIA", _("Média")),
        ("ALTA", _("Alta")),
        ("URGENTE", _("Urgente")),
    ]

    # Identificação básica
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="solicitacoes_material", verbose_name=_("Empresa")
    )
    numero_solicitacao = models.CharField(
        max_length=50, unique=True, verbose_name=_("Número da Solicitação"), help_text=_("Gerado automaticamente")
    )

    # Solicitante
    funcionario_solicitante = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="solicitacoes_feitas",
        verbose_name=_("Funcionário Solicitante"),
    )

    # Destino
    obra = models.ForeignKey(
        "obras.Obra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitacoes_material",
        verbose_name=_("Obra"),
        help_text=_("Obra onde os materiais serão utilizados"),
    )
    departamento = models.ForeignKey(
        "core.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Departamento"),
        help_text=_("Departamento solicitante (alternativo à obra)"),
    )

    # Detalhes da solicitação
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="OBRA", verbose_name=_("Tipo da Solicitação"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDENTE", verbose_name=_("Status"))
    prioridade = models.CharField(
        max_length=10, choices=PRIORIDADE_CHOICES, default="MEDIA", verbose_name=_("Prioridade")
    )

    # Datas
    data_solicitacao = models.DateTimeField(auto_now_add=True, verbose_name=_("Data da Solicitação"))
    data_necessidade = models.DateField(
        verbose_name=_("Data de Necessidade"), help_text=_("Quando os materiais são necessários")
    )

    # Aprovação
    aprovador = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitacoes_aprovadas",
        verbose_name=_("Aprovador"),
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True, verbose_name=_("Data da Aprovação"))
    observacoes_aprovacao = models.TextField(blank=True, null=True, verbose_name=_("Observações da Aprovação"))

    # Entrega
    funcionario_entrega = models.ForeignKey(
        Funcionario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas_realizadas",
        verbose_name=_("Funcionário Responsável pela Entrega"),
    )
    data_entrega = models.DateTimeField(null=True, blank=True, verbose_name=_("Data da Entrega"))

    # Textos descritivos
    justificativa = models.TextField(
        verbose_name=_("Justificativa da Solicitação"), help_text=_("Explique o motivo da solicitação")
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))
    observacoes_entrega = models.TextField(blank=True, null=True, verbose_name=_("Observações da Entrega"))

    # Valores
    valor_total_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Valor Total Estimado"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    valor_total_real = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Valor Total Real"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Controle interno
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Solicitação de Material")
        verbose_name_plural = _("Solicitações de Materiais")
        ordering = ["-data_solicitacao"]
        indexes = [
            models.Index(fields=["status", "data_solicitacao"]),
            models.Index(fields=["funcionario_solicitante", "data_solicitacao"]),
            models.Index(fields=["obra", "data_solicitacao"]),
        ]

    def __str__(self):
        return f"{self.numero_solicitacao} - {self.funcionario_solicitante.nome_completo}"

    def save(self, *args, **kwargs):
        if not self.numero_solicitacao:
            # Gerar número sequencial por empresa
            last_number = SolicitacaoMaterial.objects.filter(tenant=self.tenant).aggregate(
                models.Max("numero_solicitacao")
            )["numero_solicitacao__max"]

            if last_number:
                try:
                    number = int(last_number.split("-")[-1]) + 1
                except (ValueError, IndexError):
                    number = 1
            else:
                number = 1

            self.numero_solicitacao = f"SOL-{self.tenant.id}-{number:06d}"

        super().save(*args, **kwargs)

    @property
    def total_itens(self):
        """Total de itens na solicitação"""
        return self.itens.count()

    @property
    def status_display_class(self):
        """Classe CSS para exibição do status"""
        status_classes = {
            "RASCUNHO": "secondary",
            "PENDENTE": "warning",
            "EM_ANALISE": "info",
            "APROVADA": "success",
            "APROVADA_PARCIAL": "success",
            "REJEITADA": "danger",
            "ENTREGUE": "primary",
            "ENTREGUE_PARCIAL": "primary",
            "CANCELADA": "dark",
            "FINALIZADA": "success",
        }
        return status_classes.get(self.status, "secondary")


class ItemSolicitacaoMaterial(models.Model):
    """Itens de uma solicitação de material"""

    solicitacao = models.ForeignKey(
        SolicitacaoMaterial, on_delete=models.CASCADE, related_name="itens", verbose_name=_("Solicitação")
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, verbose_name=_("Produto"))

    # Quantidades
    quantidade_solicitada = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        verbose_name=_("Quantidade Solicitada"),
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    quantidade_aprovada = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        verbose_name=_("Quantidade Aprovada"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    quantidade_entregue = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        verbose_name=_("Quantidade Entregue"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Origem e custos
    deposito_origem = models.ForeignKey(
        "estoque.Deposito", on_delete=models.CASCADE, verbose_name=_("Depósito de Origem")
    )
    custo_unitario_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
        verbose_name=_("Custo Unitário Estimado"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    custo_unitario_real = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
        verbose_name=_("Custo Unitário Real"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Detalhes específicos
    observacoes_item = models.TextField(blank=True, null=True, verbose_name=_("Observações do Item"))
    urgente = models.BooleanField(
        default=False, verbose_name=_("Item Urgente"), help_text=_("Marca este item como urgente")
    )

    # Movimento de estoque relacionado
    movimento_estoque = models.ForeignKey(
        "estoque.MovimentoEstoque",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_solicitacao",
        verbose_name=_("Movimento de Estoque"),
    )

    class Meta:
        verbose_name = _("Item da Solicitação de Material")
        verbose_name_plural = _("Itens das Solicitações de Materiais")
        unique_together = ("solicitacao", "produto", "deposito_origem")
        ordering = ["produto__nome"]

    def __str__(self):
        return f"{self.produto.nome} - Qtd: {self.quantidade_solicitada}"

    @property
    def valor_total_estimado(self):
        """Valor total estimado do item"""
        return self.quantidade_solicitada * self.custo_unitario_estimado

    @property
    def valor_total_real(self):
        """Valor total real do item"""
        return self.quantidade_entregue * self.custo_unitario_real

    @property
    def percentual_entregue(self):
        """Percentual entregue do item aprovado"""
        if self.quantidade_aprovada > 0:
            return (self.quantidade_entregue / self.quantidade_aprovada) * 100
        return 0


class ResponsabilidadeMaterial(models.Model):
    """Controle de responsabilidade sobre materiais entregues"""

    STATUS_CHOICES = [
        ("ATIVO", _("Ativo - Sob Responsabilidade")),
        ("DEVOLVIDO", _("Devolvido")),
        ("PERDIDO", _("Perdido/Danificado")),
        ("CONSUMIDO", _("Consumido")),
        ("TRANSFERIDO", _("Transferido para Outro Funcionário")),
    ]

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="materiais_responsabilidade",
        verbose_name=_("Funcionário Responsável"),
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, verbose_name=_("Produto"))
    obra = models.ForeignKey("obras.Obra", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Obra"))
    solicitacao_origem = models.ForeignKey(
        SolicitacaoMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsabilidades_geradas",
        verbose_name=_("Solicitação de Origem"),
    )

    # Quantidades e valores
    quantidade_retirada = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        verbose_name=_("Quantidade Retirada"),
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    quantidade_devolvida = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        verbose_name=_("Quantidade Devolvida"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    valor_unitario = models.DecimalField(
        max_digits=12, decimal_places=6, verbose_name=_("Valor Unitário"), validators=[MinValueValidator(Decimal("0"))]
    )

    # Controle de datas
    data_retirada = models.DateTimeField(verbose_name=_("Data da Retirada"))
    data_previsao_devolucao = models.DateField(null=True, blank=True, verbose_name=_("Data Prevista para Devolução"))
    data_devolucao = models.DateTimeField(null=True, blank=True, verbose_name=_("Data da Devolução Real"))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ATIVO", verbose_name=_("Status"))
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    # Movimentos de estoque relacionados
    movimento_retirada = models.ForeignKey(
        "estoque.MovimentoEstoque",
        on_delete=models.SET_NULL,
        null=True,
        related_name="responsabilidades_criadas",
        verbose_name=_("Movimento de Retirada"),
    )
    movimento_devolucao = models.ForeignKey(
        "estoque.MovimentoEstoque",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsabilidades_finalizadas",
        verbose_name=_("Movimento de Devolução"),
    )

    class Meta:
        verbose_name = _("Responsabilidade sobre Material")
        verbose_name_plural = _("Responsabilidades sobre Materiais")
        ordering = ["-data_retirada"]
        indexes = [
            models.Index(fields=["funcionario", "status"]),
            models.Index(fields=["obra", "data_retirada"]),
            models.Index(fields=["status", "data_previsao_devolucao"]),
        ]

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.produto.nome} ({self.quantidade_retirada})"

    @property
    def valor_total(self):
        """Valor total sob responsabilidade"""
        return self.quantidade_retirada * self.valor_unitario

    @property
    def quantidade_pendente(self):
        """Quantidade ainda não devolvida"""
        return self.quantidade_retirada - self.quantidade_devolvida

    @property
    def em_atraso(self):
        """Verifica se está em atraso para devolução"""
        if self.status == "ATIVO" and self.data_previsao_devolucao:
            from django.utils import timezone

            return timezone.now().date() > self.data_previsao_devolucao
        return False


class ControleFerramenta(models.Model):
    """Controle específico para ferramentas com número de série"""

    CONDICAO_CHOICES = [
        ("NOVO", _("Novo")),
        ("OTIMO", _("Ótimo")),
        ("BOM", _("Bom")),
        ("REGULAR", _("Regular")),
        ("RUIM", _("Ruim")),
        ("DANIFICADO", _("Danificado")),
    ]

    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="ferramentas_controle", verbose_name=_("Funcionário")
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, verbose_name=_("Ferramenta"))

    # Identificação da ferramenta
    numero_serie = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Número de Série"))
    patrimonio = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Número do Patrimônio"))

    # Datas de controle
    data_entrega = models.DateTimeField(verbose_name=_("Data da Entrega"))
    data_previsao_devolucao = models.DateField(verbose_name=_("Data Prevista para Devolução"))
    data_devolucao_real = models.DateTimeField(null=True, blank=True, verbose_name=_("Data Real da Devolução"))

    # Condições
    condicao_entrega = models.CharField(
        max_length=20, choices=CONDICAO_CHOICES, default="BOM", verbose_name=_("Condição na Entrega")
    )
    observacoes_entrega = models.TextField(
        verbose_name=_("Observações da Entrega"), help_text=_("Descreva o estado da ferramenta na entrega")
    )
    condicao_devolucao = models.CharField(
        max_length=20, choices=CONDICAO_CHOICES, blank=True, null=True, verbose_name=_("Condição na Devolução")
    )
    observacoes_devolucao = models.TextField(blank=True, null=True, verbose_name=_("Observações da Devolução"))

    # Documentação
    termo_assinado = models.BooleanField(default=False, verbose_name=_("Termo de Responsabilidade Assinado"))
    foto_entrega = models.ImageField(
        upload_to="controle_ferramentas/entrega/", blank=True, null=True, verbose_name=_("Foto na Entrega")
    )
    foto_devolucao = models.ImageField(
        upload_to="controle_ferramentas/devolucao/", blank=True, null=True, verbose_name=_("Foto na Devolução")
    )

    # Valor e responsabilidade
    valor_ferramenta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Valor da Ferramenta"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    responsabilidade_material = models.OneToOneField(
        ResponsabilidadeMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="controle_ferramenta",
        verbose_name=_("Responsabilidade Associada"),
    )

    class Meta:
        verbose_name = _("Controle de Ferramenta")
        verbose_name_plural = _("Controles de Ferramentas")
        ordering = ["-data_entrega"]
        indexes = [
            models.Index(fields=["funcionario", "data_entrega"]),
            models.Index(fields=["data_previsao_devolucao"]),
        ]

    def __str__(self):
        descricao = f"{self.funcionario.nome_completo} - {self.produto.nome}"
        if self.numero_serie:
            descricao += f" (S/N: {self.numero_serie})"
        return descricao

    @property
    def devolvido(self):
        """Verifica se a ferramenta foi devolvida"""
        return self.data_devolucao_real is not None

    @property
    def em_atraso(self):
        """Verifica se está em atraso para devolução"""
        if not self.devolvido:
            from django.utils import timezone

            return timezone.now().date() > self.data_previsao_devolucao
        return False

    @property
    def dias_em_uso(self):
        """Calcula quantos dias a ferramenta está em uso"""
        from django.utils import timezone

        data_fim = self.data_devolucao_real or timezone.now()
        return (data_fim.date() - self.data_entrega.date()).days


class ConfiguracaoMaterial(models.Model):
    """Configurações globais do sistema de controle de materiais"""

    tenant = models.OneToOneField(
        "core.Tenant", on_delete=models.CASCADE, related_name="configuracao_material", verbose_name=_("Empresa")
    )

    # Aprovações
    aprovacao_automatica_ate_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        verbose_name=_("Aprovação Automática até Valor"),
        help_text=_("Valor máximo para aprovação automática sem supervisão"),
    )

    # Prazos
    dias_prazo_devolucao = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Dias para Prazo de Devolução"),
        help_text=_("Prazo padrão em dias para devolução de materiais"),
    )

    # Controles
    permite_retirada_sem_estoque = models.BooleanField(
        default=False,
        verbose_name=_("Permite Retirada sem Estoque"),
        help_text=_("Permite solicitar materiais mesmo sem saldo disponível"),
    )

    # Notificações
    notificar_supervisores = models.BooleanField(
        default=True,
        verbose_name=_("Notificar Supervisores"),
        help_text=_("Enviar notificações para supervisores sobre solicitações"),
    )

    # Campos obrigatórios
    campos_obrigatorios = models.JSONField(
        default=list,
        verbose_name=_("Campos Obrigatórios"),
        help_text=_("Lista de campos obrigatórios nas solicitações"),
    )

    # Auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Configuração de Material")
        verbose_name_plural = _("Configurações de Materiais")

    def __str__(self):
        return f"Configurações - {self.tenant.nome}"

from django.conf import settings
from django.db import models

# MODELOS MODERNIZADOS (antes em models_novos.py)


class Unidade(models.Model):  # Pode ser centralizado depois em cadastros_gerais
    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.CharField(max_length=100)
    fator_base = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"

    def __str__(self):
        return f"{self.codigo}" if self.codigo == self.descricao else f"{self.codigo} - {self.descricao}"


class Deposito(models.Model):
    TIPO_CHOICES = (
        ("ALMOX", "Almoxarifado"),
        ("TRANSITO", "Trânsito"),
        ("OBRA", "Obra"),
    )
    codigo = models.CharField(max_length=30, unique=True)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_depositos", null=True, blank=True
    )
    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default="ALMOX")
    obra = models.ForeignKey("obras.Obra", on_delete=models.SET_NULL, null=True, blank=True, related_name="depositos")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class EstoqueSaldo(models.Model):
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="saldos")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_saldos", null=True, blank=True
    )
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="saldos")
    quantidade = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    reservado = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    custo_medio = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("produto", "deposito")
        verbose_name = "Saldo de Estoque"
        verbose_name_plural = "Saldos de Estoque"

    def __str__(self):
        return f"Saldo(produto={self.produto_id}, deposito={self.deposito_id}, qtd={self.quantidade})"

    @property
    def disponivel(self):
        return self.quantidade - self.reservado

    # Compat: campo legado 'fisico'
    @property
    def fisico(self):
        return self.quantidade

    @property
    def valor_medio_unitario(self):
        return self.custo_medio


class MovimentoEstoque(models.Model):
    TIPO_CHOICES = (
        ("ENTRADA", "Entrada"),
        ("SAIDA", "Saída"),
        ("AJUSTE_POS", "Ajuste Positivo"),
        ("AJUSTE_NEG", "Ajuste Negativo"),
        ("TRANSFER", "Transferência"),
        ("RESERVA", "Reserva"),
        ("LIB_RESERVA", "Liberação de Reserva"),
        ("CONSUMO_BOM", "Consumo BOM"),
        ("DESCARTE", "Descarte"),
        ("PERDA", "Perda"),
        ("VENCIMENTO", "Baixa por Vencimento"),
        ("DEVOLUCAO_CLIENTE", "Devolução Cliente"),
        ("DEVOLUCAO_FORNECEDOR", "Devolução Fornecedor"),
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.PROTECT, related_name="movimentos")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_movimentos", null=True, blank=True
    )
    deposito_origem = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, null=True, blank=True, related_name="movimentos_saida"
    )
    deposito_destino = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, null=True, blank=True, related_name="movimentos_entrada"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    quantidade = models.DecimalField(max_digits=14, decimal_places=4)
    custo_unitario_snapshot = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    usuario_executante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="movimentos_executados"
    )
    solicitante_tipo = models.CharField(max_length=30, blank=True, null=True)
    solicitante_id = models.CharField(max_length=50, blank=True, null=True)
    solicitante_nome_cache = models.CharField(max_length=150, blank=True, null=True)
    ref_externa = models.CharField(max_length=80, blank=True, null=True)
    motivo = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    reverso_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentos_reversos"
    )
    aprovacao_status = models.CharField(max_length=15, default="APROVADO")  # PENDENTE, APROVADO, REJEITADO
    aplicado = models.BooleanField(default=True)
    aplicado_em = models.DateTimeField(blank=True, null=True)
    valor_estimado = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimento de Estoque"
        verbose_name_plural = "Movimentos de Estoque"
        indexes = [
            models.Index(fields=["produto", "criado_em"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["solicitante_tipo", "solicitante_id"]),
            models.Index(fields=["aprovacao_status"]),
        ]
        ordering = ["-criado_em"]
        permissions = [
            ("pode_aprovar_movimento", "Pode aprovar/rejeitar movimentos de estoque sensíveis"),
            ("pode_operar_movimento", "Pode executar operações de entrada/saída/transferência"),
            ("pode_consumir_bom", "Pode registrar consumo de BOM"),
            ("pode_gerenciar_reabastecimento", "Pode criar/alterar regras de reabastecimento"),
            ("pode_gerenciar_inventario_ciclico", "Pode criar/alterar inventários cíclicos"),
            ("pode_gerenciar_picking", "Pode criar e operar pedidos de separação"),
        ]

    def __str__(self):
        return f"Mov({self.tipo} prod={self.produto_id} qtd={self.quantidade})"


## REMOVIDO: definição duplicada de EstoqueSaldo substituída por versão unificada acima


class MovimentoEvidencia(models.Model):
    movimento = models.ForeignKey(MovimentoEstoque, on_delete=models.CASCADE, related_name="evidencias")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_movimento_evidencias", null=True, blank=True
    )
    arquivo = models.FileField(upload_to="estoque/movimentos/evidencias/")
    descricao = models.CharField(max_length=255, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"EvidenciaMov {self.movimento_id}"


class ReservaEstoque(models.Model):
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="reservas")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_reservas", null=True, blank=True
    )
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="reservas")
    quantidade = models.DecimalField(max_digits=14, decimal_places=4)
    origem_tipo = models.CharField(max_length=30)
    origem_id = models.CharField(max_length=60, blank=True, null=True)
    status = models.CharField(max_length=15, default="ATIVA")  # ATIVA, CONSUMIDA, CANCELADA, EXPIRADA
    expira_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    # Campos voláteis (não persistidos) para compatibilidade
    motivo = None  # usado em logs antigos
    observacoes = None
    criado_por = None
    cancelada_em = None
    consumida_em = None

    class Meta:
        indexes = [
            models.Index(fields=["produto", "deposito"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expira_em"]),
        ]

    def __str__(self):
        return f"Reserva(prod={self.produto_id} dep={self.deposito_id} qtd={self.quantidade} status={self.status})"

    def __init__(self, *args, **kwargs):
        # Consumir kwargs legados que não são campos persistidos
        for legacy in ["motivo", "observacoes", "criado_por", "cancelada_em", "consumida_em"]:
            if legacy in kwargs:
                setattr(self, legacy, kwargs.pop(legacy))
        super().__init__(*args, **kwargs)

    def agregar_quantidade(self, adicional):
        from decimal import Decimal

        adicional = Decimal(str(adicional))
        self.quantidade += adicional
        # Evita update_fields (não sabemos se teste mexe em outros atributos), salva completo
        super().save()
        return self


class InventarioCiclico(models.Model):
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="inventarios_ciclicos")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_inventarios_ciclicos", null=True, blank=True
    )
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="inventarios_ciclicos")
    periodicidade_dias = models.PositiveIntegerField(default=30)
    ultima_contagem = models.DateTimeField(blank=True, null=True)
    proxima_contagem = models.DateTimeField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("produto", "deposito")
        indexes = [
            models.Index(fields=["proxima_contagem"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return f"InvCiclico prod={self.produto_id} dep={self.deposito_id} prox={self.proxima_contagem}"


class RegraReabastecimento(models.Model):
    ESTRATEGIA_CHOICES = (
        ("FIXO", "Fixo"),
        ("MEDIA_CONSUMO", "Média Consumo"),
        ("FORECAST", "Forecast"),
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="regras_reabastecimento")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_regras_reabastecimento", null=True, blank=True
    )
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="regras_reabastecimento")
    estoque_min = models.DecimalField(max_digits=14, decimal_places=4)
    estoque_max = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)
    lote_economico = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)
    lead_time_dias = models.PositiveIntegerField(default=0)
    estrategia = models.CharField(max_length=20, choices=ESTRATEGIA_CHOICES, default="FIXO")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("produto", "deposito")
        indexes = [
            models.Index(fields=["ativo"]),
            models.Index(fields=["produto", "deposito"]),
        ]

    def __str__(self):
        return f"RegraReabast prod={self.produto_id} dep={self.deposito_id} min={self.estoque_min}"


class Lote(models.Model):
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="lotes")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_lotes", null=True, blank=True
    )
    codigo = models.CharField(max_length=40)
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="lotes", null=True, blank=True)
    validade = models.DateField(blank=True, null=True)
    quantidade_atual = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    quantidade_reservada = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("produto", "codigo")
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["validade"]),
        ]

    def __str__(self):
        return f"Lote {self.codigo} prod={self.produto_id}"


class NumeroSerie(models.Model):
    STATUS_CHOICES = (
        ("ATIVO", "Ativo"),
        ("MOVIMENTADO", "Movimentado"),
        ("BAIXADO", "Baixado"),
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="numeros_serie")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_numeros_serie", null=True, blank=True
    )
    codigo = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="ATIVO")
    deposito_atual = models.ForeignKey(
        Deposito, on_delete=models.SET_NULL, null=True, blank=True, related_name="numeros_serie"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"NS {self.codigo} ({self.status})"


class MovimentoLote(models.Model):
    movimento = models.ForeignKey(MovimentoEstoque, on_delete=models.CASCADE, related_name="lotes_movimentados")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="movimentos")
    quantidade = models.DecimalField(max_digits=14, decimal_places=4)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["lote"]),
        ]

    def __str__(self):
        return f"MovLote mov={self.movimento_id} lote={self.lote_id} qtd={self.quantidade}"


class MovimentoNumeroSerie(models.Model):
    movimento = models.ForeignKey(MovimentoEstoque, on_delete=models.CASCADE, related_name="numeros_serie_movimentados")
    numero_serie = models.ForeignKey(NumeroSerie, on_delete=models.PROTECT, related_name="movimentos")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["numero_serie"]),
        ]

    def __str__(self):
        return f"MovNS mov={self.movimento_id} ns={self.numero_serie_id}"


class LogAuditoriaEstoque(models.Model):
    movimento = models.ForeignKey(MovimentoEstoque, on_delete=models.CASCADE, related_name="logs")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_logs_auditoria", null=True, blank=True
    )
    snapshot_antes = models.JSONField(blank=True, null=True)
    snapshot_depois = models.JSONField(blank=True, null=True)
    hash_previo = models.CharField(max_length=128, blank=True, null=True)
    hash_atual = models.CharField(max_length=128, blank=True, null=True)
    evidencias_ids = models.JSONField(blank=True, null=True)  # IDs das evidências anexadas
    solicitante_nome_cache = models.CharField(max_length=150, blank=True, null=True)
    tipo_especial = models.CharField(max_length=20, blank=True, null=True)  # DESCARTE, PERDA, VENCIMENTO
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="logs_estoque"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["tipo_especial"]),
            models.Index(fields=["hash_atual"]),
        ]

    def __str__(self):
        return f"LogMov {self.movimento_id}"


class CamadaCusto(models.Model):
    produto = models.ForeignKey("produtos.Produto", on_delete=models.CASCADE, related_name="camadas_custo")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_camadas_custo", null=True, blank=True
    )
    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="camadas_custo")
    quantidade_restante = models.DecimalField(max_digits=14, decimal_places=4)
    custo_unitario = models.DecimalField(max_digits=14, decimal_places=6)
    ordem = models.BigAutoField(primary_key=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["produto", "deposito"]),
        ]
        ordering = ["ordem"]

    def __str__(self):
        return f"Camada(prod={self.produto_id} dep={self.deposito_id} qtd={self.quantidade_restante} custo={self.custo_unitario})"


class PedidoSeparacao(models.Model):
    PRIORIDADE_CHOICES = (
        ("BAIXA", "Baixa"),
        ("NORMAL", "Normal"),
        ("ALTA", "Alta"),
        ("URGENTE", "Urgente"),
    )
    STATUS_CHOICES = (
        ("ABERTO", "Aberto"),
        ("EM_PREPARACAO", "Em Preparação"),
        ("PRONTO", "Pronto"),
        ("RETIRADO", "Retirado"),
        ("CANCELADO", "Cancelado"),
        ("EXPIRADO", "Expirado"),
    )
    codigo = models.CharField(max_length=40, unique=True, blank=True, null=True)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_pedidos_separacao", null=True, blank=True
    )
    solicitante_tipo = models.CharField(max_length=30)
    solicitante_id = models.CharField(max_length=60)
    solicitante_nome_cache = models.CharField(max_length=150)
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default="NORMAL")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="ABERTO")
    data_limite = models.DateTimeField(blank=True, null=True)
    criado_por_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="pedidos_criados"
    )
    operador_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos_assumidos"
    )
    itens_totais = models.PositiveIntegerField(default=0)
    itens_pendentes = models.PositiveIntegerField(default=0)
    itens_separados = models.PositiveIntegerField(default=0)
    permitir_retirada_parcial = models.BooleanField(default=False)
    canal_origem = models.CharField(max_length=20, default="PORTAL")
    motivo_cancelamento = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    inicio_preparo = models.DateTimeField(blank=True, null=True)
    pronto_em = models.DateTimeField(blank=True, null=True)
    retirado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "prioridade"]),
            models.Index(fields=["data_limite"]),
            models.Index(fields=["solicitante_tipo", "solicitante_id"]),
        ]
        ordering = ["-criado_em"]

    def __str__(self):
        return f"PedidoSep {self.codigo or self.id}"


class PedidoSeparacaoItem(models.Model):
    STATUS_CHOICES = (
        ("PENDENTE", "Pendente"),
        ("SEPARADO", "Separado"),
        ("INDISPONIVEL", "Indisponível"),
        ("PARCIAL", "Parcial"),
        ("CANCELADO", "Cancelado"),
    )
    pedido = models.ForeignKey(PedidoSeparacao, on_delete=models.CASCADE, related_name="itens")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_pedidos_separacao_itens", null=True, blank=True
    )
    produto = models.ForeignKey("produtos.Produto", on_delete=models.PROTECT)
    deposito = models.ForeignKey(
        Deposito, on_delete=models.SET_NULL, null=True, blank=True, related_name="itens_picking"
    )
    quantidade_solicitada = models.DecimalField(max_digits=14, decimal_places=4)
    quantidade_separada = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unidade = models.ForeignKey(Unidade, on_delete=models.SET_NULL, null=True, blank=True)
    observacao = models.CharField(max_length=255, blank=True, null=True)
    reserva = models.ForeignKey(
        ReservaEstoque, on_delete=models.SET_NULL, null=True, blank=True, related_name="itens_picking"
    )
    status_item = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDENTE")
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status_item"]),
        ]

    def __str__(self):
        return f"ItemPedidoSep pedido={self.pedido_id} prod={self.produto_id}"


class PedidoSeparacaoMensagem(models.Model):
    pedido = models.ForeignKey(PedidoSeparacao, on_delete=models.CASCADE, related_name="mensagens")
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="estoque_pedidos_separacao_mensagens",
        null=True,
        blank=True,
    )
    autor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    autor_tipo = models.CharField(max_length=30, blank=True, null=True)
    autor_id = models.CharField(max_length=60, blank=True, null=True)
    texto = models.TextField()
    importante = models.BooleanField(default=False)
    anexos_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]

    def __str__(self):
        return f"MsgPedidoSep {self.pedido_id}"


class PedidoSeparacaoAnexo(models.Model):
    mensagem = models.ForeignKey(PedidoSeparacaoMensagem, on_delete=models.CASCADE, related_name="anexos")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="estoque_pedidos_separacao_anexos", null=True, blank=True
    )
    arquivo = models.FileField(upload_to="pedidos_separacao/anexos/")
    nome_original = models.CharField(max_length=255)
    tamanho_bytes = models.BigIntegerField()
    tipo_mime = models.CharField(max_length=120)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AnexoMsg {self.mensagem_id}"

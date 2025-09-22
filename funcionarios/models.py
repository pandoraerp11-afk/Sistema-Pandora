# funcionarios/models.py

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CustomUser, Department, Tenant, TimestampedModel


class Funcionario(TimestampedModel):
    SEXO_CHOICES = [("M", "Masculino"), ("F", "Feminino"), ("O", "Outro")]
    ESTADO_CIVIL_CHOICES = [
        ("SOLTEIRO", "Solteiro(a)"),
        ("CASADO", "Casado(a)"),
        ("DIVORCIADO", "Divorciado(a)"),
        ("VIUVO", "Viúvo(a)"),
        ("UNIAO_ESTAVEL", "União Estável"),
    ]
    TIPO_CONTRATO_CHOICES = [
        ("CLT", "CLT"),
        ("PJ", "Pessoa Jurídica"),
        ("ESTAGIO", "Estágio"),
        ("APRENDIZ", "Aprendiz"),
        ("TEMPORARIO", "Temporário"),
    ]
    ESCOLARIDADE_CHOICES = [
        ("FUNDAMENTAL_INCOMPLETO", "Ensino Fundamental Incompleto"),
        ("FUNDAMENTAL_COMPLETO", "Ensino Fundamental Completo"),
        ("MEDIO_INCOMPLETO", "Ensino Médio Incompleto"),
        ("MEDIO_COMPLETO", "Ensino Médio Completo"),
        ("SUPERIOR_INCOMPLETO", "Ensino Superior Incompleto"),
        ("SUPERIOR_COMPLETO", "Ensino Superior Completo"),
        ("POS_GRADUACAO", "Pós-Graduação"),
        ("MESTRADO", "Mestrado"),
        ("DOUTORADO", "Doutorado"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="funcionarios", verbose_name=_("Empresa"))
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionario_profile",
        verbose_name=_("Usuário do Sistema (Opcional)"),
    )

    # Informações pessoais
    nome_completo = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, verbose_name=_("CPF"))
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))
    rg_orgao_emissor = models.CharField(max_length=20, blank=True, null=True, verbose_name=("Órgão Emissor RG"))
    rg_data_emissao = models.DateField(blank=True, null=True, verbose_name=("Data Emissão RG"))
    data_nascimento = models.DateField(verbose_name=_("Data de Nascimento"))
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, verbose_name=_("Sexo"))
    estado_civil = models.CharField(
        max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True, verbose_name=_("Estado Civil")
    )
    nacionalidade = models.CharField(max_length=100, default="Brasileira", verbose_name=_("Nacionalidade"))
    naturalidade = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Naturalidade (Cidade de Nascimento)")
    )
    nome_mae = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Nome da Mãe"))
    nome_pai = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Nome do Pai"))
    profissao = models.CharField(max_length=150, blank=True, null=True, verbose_name=_("Profissão"))
    escolaridade = models.CharField(
        max_length=30, choices=ESCOLARIDADE_CHOICES, blank=True, null=True, verbose_name=_("Escolaridade")
    )

    # Contato
    email_pessoal = models.EmailField(blank=True, null=True, verbose_name=_("E-mail Pessoal"))
    telefone_pessoal = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone Pessoal"))
    telefone_secundario = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone Secundário"))
    telefone_emergencia = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Telefone de Emergência")
    )
    contato_emergencia = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Contato de Emergência")
    )

    # Endereço
    endereco_logradouro = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Logradouro"))
    endereco_numero = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Número"))
    endereco_complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Complemento"))
    endereco_bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Bairro"))
    endereco_cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cidade"))
    endereco_uf = models.CharField(max_length=2, blank=True, null=True, verbose_name=_("UF"))
    endereco_cep = models.CharField(max_length=9, blank=True, null=True, verbose_name=_("CEP"))
    endereco_pais = models.CharField(max_length=100, blank=True, null=True, default="Brasil", verbose_name=_("País"))

    # Informações trabalhistas
    data_admissao = models.DateField(verbose_name=_("Data de Admissão"))
    data_demissao = models.DateField(blank=True, null=True, verbose_name=_("Data de Demissão"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    motivo_demissao = models.TextField(blank=True, null=True, verbose_name=_("Motivo da Demissão/Desligamento"))

    cargo = models.CharField(max_length=100, verbose_name=_("Cargo"))
    departamento = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Departamento")
    )
    tipo_contrato = models.CharField(
        max_length=20, choices=TIPO_CONTRATO_CHOICES, default="CLT", verbose_name=_("Tipo de Contrato")
    )
    jornada_trabalho_horas = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Jornada de Trabalho (horas/dia)"),
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("24.00"))],
    )
    horario_entrada = models.TimeField(blank=True, null=True, verbose_name=_("Horário de Entrada"))
    horario_saida = models.TimeField(blank=True, null=True, verbose_name=_("Horário de Saída"))
    intervalo_inicio = models.TimeField(blank=True, null=True, verbose_name=_("Início Intervalo"))
    intervalo_fim = models.TimeField(blank=True, null=True, verbose_name=_("Fim Intervalo"))

    # Informações salariais
    salario_base = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Salário Base"), validators=[MinValueValidator(Decimal("0.01"))]
    )
    cnpj_prestador = models.CharField(max_length=18, blank=True, null=True, verbose_name=_("CNPJ (Prestador PJ/MEI)"))
    PJ_CATEGORIA_CHOICES = [("MEI", "MEI"), ("SOCIEDADE", "Sociedade / Empresa"), ("AUTONOMO", "Autônomo (RPA)")]
    pj_categoria = models.CharField(
        max_length=20, choices=PJ_CATEGORIA_CHOICES, blank=True, null=True, verbose_name=_("Categoria PJ")
    )

    # Informações bancárias
    banco = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Banco"))
    agencia = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Agência"))
    conta = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Conta"))
    tipo_conta = models.CharField(
        max_length=20,
        choices=[("CORRENTE", "Corrente"), ("POUPANCA", "Poupança")],
        blank=True,
        null=True,
        verbose_name=_("Tipo de Conta"),
    )

    # Documentos trabalhistas
    pis = models.CharField(max_length=14, blank=True, null=True, verbose_name=_("PIS/PASEP"))
    ctps = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("CTPS"))
    titulo_eleitor = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Título de Eleitor"))
    reservista = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Certificado de Reservista"))

    # Dependentes
    numero_dependentes = models.PositiveIntegerField(default=0, verbose_name=_("Número de Dependentes"))

    # Observações
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("funcionário")
        verbose_name_plural = _("funcionários")
        ordering = ["nome_completo"]
        unique_together = ("tenant", "cpf")

    def __str__(self):
        return self.nome_completo

    @property
    def idade(self):
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.data_nascimento.year
            - ((today.month, today.day) < (self.data_nascimento.month, self.data_nascimento.day))
        )

    @property
    def tempo_empresa(self):
        from datetime import date

        today = date.today()
        data_fim = self.data_demissao if self.data_demissao else today
        return data_fim - self.data_admissao

    def get_salario_atual(self):
        """Retorna o salário atual do funcionário baseado no histórico"""
        ultimo_historico = self.historico_salarios.order_by("-data_vigencia").first()
        return ultimo_historico.valor_salario if ultimo_historico else self.salario_base

    def save(self, *args, **kwargs):
        # Ajusta automaticamente o campo ativo conforme existência de data_demissao
        self.ativo = not self.data_demissao
        super().save(*args, **kwargs)

    @property
    def status(self):
        return "DESLIGADO" if self.data_demissao else "ATIVO"


class FuncionarioHorario(models.Model):
    DIAS_SEMANA = [
        (0, "Segunda"),
        (1, "Terça"),
        (2, "Quarta"),
        (3, "Quinta"),
        (4, "Sexta"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    ordem = models.PositiveSmallIntegerField(
        default=1, help_text="Permite múltiplos blocos no mesmo dia (1 = principal)"
    )
    entrada = models.TimeField(blank=True, null=True)
    saida = models.TimeField(blank=True, null=True)
    intervalo_inicio = models.TimeField(blank=True, null=True)
    intervalo_fim = models.TimeField(blank=True, null=True)
    horas_previstas = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("funcionario", "dia_semana", "ordem")
        ordering = ["funcionario", "dia_semana", "ordem"]

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.get_dia_semana_display()} (bloco {self.ordem})"

    def calcular_horas(self):
        from datetime import date, datetime

        if self.entrada and self.saida:
            dt = date.today()
            total = datetime.combine(dt, self.saida) - datetime.combine(dt, self.entrada)
            if self.intervalo_inicio and self.intervalo_fim:
                total -= datetime.combine(dt, self.intervalo_fim) - datetime.combine(dt, self.intervalo_inicio)
            horas = total.total_seconds() / 3600.0
            return round(horas, 2)
        return None

    def save(self, *args, **kwargs):
        self.horas_previstas = self.calcular_horas()
        super().save(*args, **kwargs)


class FuncionarioRemuneracaoRegra(TimestampedModel):
    TIPO_REGRA_CHOICES = [
        ("FIXO_MENSAL", "Salário Fixo Mensal"),
        ("HORA", "Valor por Hora"),
        ("TAREFA", "Valor por Tarefa"),
        ("PROCEDIMENTO_PERCENTUAL", "% sobre Procedimento"),
        ("PROCEDIMENTO_FIXO", "Valor Fixo por Procedimento"),
        ("COMISSAO_PERCENTUAL", "% de Comissão"),
        ("COMISSAO_FIXA", "Comissão Fixa"),
    ]
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="regras_remuneracao", verbose_name=_("Empresa")
    )
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="regras_remuneracao", verbose_name=_("Funcionário")
    )
    tipo_regra = models.CharField(max_length=40, choices=TIPO_REGRA_CHOICES, verbose_name=_("Tipo de Regra"))
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Descrição"))
    valor_base = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Valor Base")
    )
    percentual = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name=_("Percentual (%)")
    )
    codigo_procedimento = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Código Procedimento (Opcional)")
    )
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))
    vigencia_inicio = models.DateField(blank=True, null=True, verbose_name=_("Início Vigência"))
    vigencia_fim = models.DateField(blank=True, null=True, verbose_name=_("Fim Vigência"))

    class Meta:
        verbose_name = _("regra de remuneração")
        verbose_name_plural = _("regras de remuneração")
        ordering = ["funcionario", "tipo_regra", "-vigencia_inicio"]

    def __str__(self):
        base = self.get_tipo_regra_display()
        if self.percentual:
            return f"{base} {self.percentual}%"
        if self.valor_base:
            return f"{base} R$ {self.valor_base}"
        return base


class Ferias(TimestampedModel):
    STATUS_FERIAS_CHOICES = [
        ("AGENDADA", "Agendada"),
        ("EM_ANDAMENTO", "Em Andamento"),
        ("CONCLUIDA", "Concluída"),
        ("CANCELADA", "Cancelada"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="ferias", verbose_name=_("Empresa"))
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="ferias", verbose_name=_("Funcionário")
    )

    periodo_aquisitivo_inicio = models.DateField(verbose_name=_("Início Período Aquisitivo"))
    periodo_aquisitivo_fim = models.DateField(verbose_name=_("Fim Período Aquisitivo"))

    data_inicio = models.DateField(verbose_name=_("Data de Início das Férias"))
    data_fim = models.DateField(verbose_name=_("Data de Fim das Férias"))
    dias_gozados = models.PositiveIntegerField(
        verbose_name=_("Dias Gozados"), validators=[MinValueValidator(1), MaxValueValidator(30)]
    )

    abono_pecuniario = models.BooleanField(default=False, verbose_name=_("Abono Pecuniário (Venda de Férias)"))
    dias_abono = models.PositiveIntegerField(
        default=0, verbose_name=_("Dias de Abono"), validators=[MinValueValidator(0), MaxValueValidator(10)]
    )

    data_pagamento = models.DateField(blank=True, null=True, verbose_name=_("Data de Pagamento"))
    valor_pago = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Valor Pago"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    status = models.CharField(
        max_length=20, choices=STATUS_FERIAS_CHOICES, default="AGENDADA", verbose_name=_("Status")
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("férias")
        verbose_name_plural = _("férias")
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"Férias de {self.funcionario.nome_completo} ({self.data_inicio} a {self.data_fim})"

    @property
    def total_dias(self):
        return self.dias_gozados + self.dias_abono

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.data_fim <= self.data_inicio:
            raise ValidationError(_("A data de fim deve ser posterior à data de início."))
        if self.abono_pecuniario and self.dias_abono == 0:
            raise ValidationError(_("Quando há abono pecuniário, deve ser informado o número de dias."))


class DecimoTerceiro(TimestampedModel):
    TIPO_PARCELA_CHOICES = [("PRIMEIRA", "Primeira Parcela"), ("SEGUNDA", "Segunda Parcela"), ("INTEGRAL", "Integral")]
    STATUS_PAGAMENTO_CHOICES = [("PENDENTE", "Pendente"), ("PAGO", "Pago"), ("CANCELADO", "Cancelado")]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="decimo_terceiro", verbose_name=_("Empresa")
    )
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="decimo_terceiro", verbose_name=_("Funcionário")
    )

    ano_referencia = models.PositiveIntegerField(verbose_name=_("Ano de Referência"))
    tipo_parcela = models.CharField(max_length=10, choices=TIPO_PARCELA_CHOICES, verbose_name=_("Tipo de Parcela"))

    meses_trabalhados = models.PositiveIntegerField(
        verbose_name=_("Meses Trabalhados"), validators=[MinValueValidator(1), MaxValueValidator(12)]
    )

    valor_bruto = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Valor Bruto"), validators=[MinValueValidator(Decimal("0.01"))]
    )
    desconto_inss = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Desconto INSS"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    desconto_irrf = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Desconto IRRF"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    outros_descontos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Outros Descontos"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    valor_liquido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Valor Líquido"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    data_pagamento = models.DateField(verbose_name=_("Data de Pagamento"))
    status = models.CharField(
        max_length=10, choices=STATUS_PAGAMENTO_CHOICES, default="PENDENTE", verbose_name=_("Status de Pagamento")
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("décimo terceiro")
        verbose_name_plural = _("décimos terceiros")
        ordering = ["-ano_referencia", "funcionario__nome_completo"]
        unique_together = ("tenant", "funcionario", "ano_referencia", "tipo_parcela")

    def __str__(self):
        return f"13º de {self.funcionario.nome_completo} - {self.ano_referencia} ({self.get_tipo_parcela_display()})"

    @property
    def total_descontos(self):
        return self.desconto_inss + self.desconto_irrf + self.outros_descontos

    def save(self, *args, **kwargs):
        # Calcula automaticamente o valor líquido
        self.valor_liquido = self.valor_bruto - self.total_descontos
        super().save(*args, **kwargs)


class Folga(TimestampedModel):
    TIPO_FOLGA_CHOICES = [
        ("JUSTIFICADA", "Justificada"),
        ("INJUSTIFICADA", "Injustificada"),
        ("BANCO_HORAS", "Banco de Horas"),
        ("FERIADO", "Feriado"),
        ("LICENCA_MEDICA", "Licença Médica"),
        ("LICENCA_MATERNIDADE", "Licença Maternidade"),
        ("LICENCA_PATERNIDADE", "Licença Paternidade"),
        ("LUTO", "Luto"),
        ("CASAMENTO", "Casamento"),
        ("DOACAO_SANGUE", "Doação de Sangue"),
    ]
    STATUS_FOLGA_CHOICES = [
        ("SOLICITADA", "Solicitada"),
        ("APROVADA", "Aprovada"),
        ("REJEITADA", "Rejeitada"),
        ("CONCLUIDA", "Concluída"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="folgas", verbose_name=_("Empresa"))
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="folgas", verbose_name=_("Funcionário")
    )

    data_inicio = models.DateField(verbose_name=_("Data de Início da Folga"))
    data_fim = models.DateField(verbose_name=_("Data de Fim da Folga"))
    tipo_folga = models.CharField(max_length=20, choices=TIPO_FOLGA_CHOICES, verbose_name=_("Tipo de Folga"))

    motivo = models.TextField(blank=True, null=True, verbose_name=_("Motivo"))
    documento_comprobatorio = models.FileField(
        upload_to="folgas_documentos/", blank=True, null=True, verbose_name=_("Documento Comprobatório")
    )

    status = models.CharField(
        max_length=20, choices=STATUS_FOLGA_CHOICES, default="SOLICITADA", verbose_name=_("Status")
    )
    aprovado_por = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Aprovado Por")
    )
    data_aprovacao = models.DateField(blank=True, null=True, verbose_name=_("Data de Aprovação/Rejeição"))
    observacoes_aprovacao = models.TextField(blank=True, null=True, verbose_name=_("Observações da Aprovação"))

    class Meta:
        verbose_name = _("folga")
        verbose_name_plural = _("folgas")
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"Folga de {self.funcionario.nome_completo} ({self.data_inicio} a {self.data_fim})"

    @property
    def dias_folga(self):
        return (self.data_fim - self.data_inicio).days + 1

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.data_fim < self.data_inicio:
            raise ValidationError(_("A data de fim deve ser igual ou posterior à data de início."))


class CartaoPonto(TimestampedModel):
    TIPO_REGISTRO_CHOICES = [
        ("ENTRADA", "Entrada"),
        ("SAIDA", "Saída"),
        ("INICIO_ALMOCO", "Início Almoço"),
        ("FIM_ALMOCO", "Fim Almoço"),
        ("ENTRADA_EXTRA", "Entrada Hora Extra"),
        ("SAIDA_EXTRA", "Saída Hora Extra"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="cartao_ponto", verbose_name=_("Empresa"))
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="cartao_ponto", verbose_name=_("Funcionário")
    )

    data_hora_registro = models.DateTimeField(verbose_name=_("Data e Hora do Registro"))
    tipo_registro = models.CharField(max_length=20, choices=TIPO_REGISTRO_CHOICES, verbose_name=_("Tipo de Registro"))

    ip_origem = models.GenericIPAddressField(blank=True, null=True, verbose_name=_("IP de Origem"))
    localizacao = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Localização (GPS)"))

    justificativa = models.TextField(blank=True, null=True, verbose_name=_("Justificativa"))
    aprovado = models.BooleanField(default=True, verbose_name=_("Aprovado"))
    aprovado_por = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pontos_aprovados",
        verbose_name=_("Aprovado Por"),
    )

    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("cartão de ponto")
        verbose_name_plural = _("cartões de ponto")
        ordering = ["-data_hora_registro"]

    def __str__(self):
        return f"Ponto de {self.funcionario.nome_completo} em {self.data_hora_registro.strftime('%d/%m/%Y %H:%M')}"


class Beneficio(TimestampedModel):
    TIPO_BENEFICIO_CHOICES = [
        ("INSS", "INSS"),
        ("FGTS", "FGTS"),
        ("IRRF", "Imposto de Renda Retido na Fonte"),
        ("VALE_TRANSPORTE", "Vale Transporte"),
        ("VALE_ALIMENTACAO", "Vale Alimentação"),
        ("VALE_REFEICAO", "Vale Refeição"),
        ("PLANO_SAUDE", "Plano de Saúde"),
        ("PLANO_ODONTOLOGICO", "Plano Odontológico"),
        ("SEGURO_VIDA", "Seguro de Vida"),
        ("AUXILIO_CRECHE", "Auxílio Creche"),
        ("AUXILIO_EDUCACAO", "Auxílio Educação"),
        ("PARTICIPACAO_LUCROS", "Participação nos Lucros"),
        ("COMISSAO", "Comissão"),
        ("BONUS", "Bônus"),
        ("ADIANTAMENTO", "Adiantamento"),
        ("DESCONTO_ATRASO", "Desconto por Atraso"),
        ("DESCONTO_FALTA", "Desconto por Falta"),
        ("OUTRO", "Outro"),
    ]
    CATEGORIA_CHOICES = [("BENEFICIO", "Benefício"), ("DESCONTO", "Desconto"), ("PROVENTO", "Provento")]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="beneficios", verbose_name=_("Empresa"))
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="beneficios", verbose_name=_("Funcionário")
    )

    tipo_beneficio = models.CharField(
        max_length=50, choices=TIPO_BENEFICIO_CHOICES, verbose_name=_("Tipo de Benefício/Desconto")
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, verbose_name=_("Categoria"))

    valor = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Valor"), validators=[MinValueValidator(Decimal("0.01"))]
    )
    data_referencia = models.DateField(verbose_name=_("Data de Referência"))

    recorrente = models.BooleanField(default=False, verbose_name=_("Recorrente"))
    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))

    observacoes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))

    class Meta:
        verbose_name = _("benefício/desconto")
        verbose_name_plural = _("benefícios/descontos")
        ordering = ["-data_referencia", "tipo_beneficio"]

    def __str__(self):
        return f"{self.get_tipo_beneficio_display()} para {self.funcionario.nome_completo} em {self.data_referencia.strftime('%m/%Y')}"


class SalarioHistorico(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="historico_salarios", verbose_name=_("Empresa")
    )
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="historico_salarios", verbose_name=_("Funcionário")
    )

    data_vigencia = models.DateField(verbose_name=_("Data de Vigência"))
    valor_salario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Valor do Salário"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    motivo_alteracao = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Motivo da Alteração"))

    alterado_por = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Alterado Por")
    )

    class Meta:
        verbose_name = _("histórico salarial")
        verbose_name_plural = _("históricos salariais")
        ordering = ["-data_vigencia"]

    def __str__(self):
        return f"Salário de {self.funcionario.nome_completo} em {self.data_vigencia}: R$ {self.valor_salario}"


class Dependente(TimestampedModel):
    TIPO_DEPENDENTE_CHOICES = [
        ("FILHO", "Filho(a)"),
        ("CONJUGE", "Cônjuge"),
        ("PAI", "Pai"),
        ("MAE", "Mãe"),
        ("OUTRO", "Outro"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="dependentes", verbose_name=_("Empresa"))
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="dependentes", verbose_name=_("Funcionário")
    )

    nome_completo = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name=_("CPF"))
    data_nascimento = models.DateField(verbose_name=_("Data de Nascimento"))
    tipo_dependente = models.CharField(
        max_length=20, choices=TIPO_DEPENDENTE_CHOICES, verbose_name=_("Tipo de Dependente")
    )

    dependente_ir = models.BooleanField(default=True, verbose_name=_("Dependente para IR"))
    dependente_salario_familia = models.BooleanField(default=True, verbose_name=_("Dependente para Salário Família"))

    class Meta:
        verbose_name = _("dependente")
        verbose_name_plural = _("dependentes")
        ordering = ["nome_completo"]

    def __str__(self):
        return f"{self.nome_completo} - {self.get_tipo_dependente_display()} de {self.funcionario.nome_completo}"

    @property
    def idade(self):
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.data_nascimento.year
            - ((today.month, today.day) < (self.data_nascimento.month, self.data_nascimento.day))
        )


class HorarioTrabalho(TimestampedModel):
    DIAS_SEMANA_CHOICES = [
        ("SEGUNDA", "Segunda-feira"),
        ("TERCA", "Terça-feira"),
        ("QUARTA", "Quarta-feira"),
        ("QUINTA", "Quinta-feira"),
        ("SEXTA", "Sexta-feira"),
        ("SABADO", "Sábado"),
        ("DOMINGO", "Domingo"),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="horarios_trabalho", verbose_name=_("Empresa")
    )
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name="horarios_trabalho", verbose_name=_("Funcionário")
    )

    dia_semana = models.CharField(max_length=10, choices=DIAS_SEMANA_CHOICES, verbose_name=_("Dia da Semana"))

    hora_entrada = models.TimeField(verbose_name=_("Hora de Entrada"))
    hora_saida = models.TimeField(verbose_name=_("Hora de Saída"))
    hora_inicio_almoco = models.TimeField(blank=True, null=True, verbose_name=_("Hora Início Almoço"))
    hora_fim_almoco = models.TimeField(blank=True, null=True, verbose_name=_("Hora Fim Almoço"))

    ativo = models.BooleanField(default=True, verbose_name=_("Ativo"))

    class Meta:
        verbose_name = _("horário de trabalho")
        verbose_name_plural = _("horários de trabalho")
        ordering = ["funcionario__nome_completo", "dia_semana"]
        unique_together = ("tenant", "funcionario", "dia_semana")

    def __str__(self):
        return f"Horário de {self.funcionario.nome_completo} - {self.get_dia_semana_display()}"

    @property
    def horas_trabalhadas(self):
        from datetime import datetime, timedelta

        entrada = datetime.combine(datetime.today(), self.hora_entrada)
        saida = datetime.combine(datetime.today(), self.hora_saida)

        if self.hora_inicio_almoco and self.hora_fim_almoco:
            inicio_almoco = datetime.combine(datetime.today(), self.hora_inicio_almoco)
            fim_almoco = datetime.combine(datetime.today(), self.hora_fim_almoco)
            almoco = fim_almoco - inicio_almoco
        else:
            almoco = timedelta(0)

        total = saida - entrada - almoco
        return total.total_seconds() / 3600  # retorna em horas


# ============================================================================
# INTEGRAÇÃO COM ESTOQUE - CONTROLE DE MATERIAIS
# ============================================================================

# bi/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse

User = get_user_model()


class Indicador(models.Model):
    TIPO_CHOICES = [
        ("financeiro", "Financeiro"),
        ("produtividade", "Produtividade"),
        ("qualidade", "Qualidade"),
        ("eficiencia", "Eficiência"),
        ("vendas", "Vendas"),
        ("marketing", "Marketing"),
        ("operacional", "Operacional"),
        ("rh", "Recursos Humanos"),
        ("outro", "Outro"),
    ]

    PERIODO_CHOICES = [
        ("diario", "Diário"),
        ("semanal", "Semanal"),
        ("mensal", "Mensal"),
        ("trimestral", "Trimestral"),
        ("anual", "Anual"),
    ]

    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
        ("arquivado", "Arquivado"),
    ]

    nome = models.CharField(max_length=200, verbose_name="Nome do Indicador")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    valor = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor")
    meta = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Meta")
    data = models.DateField(verbose_name="Data")
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default="outro", verbose_name="Tipo")
    periodo = models.CharField(max_length=50, choices=PERIODO_CHOICES, default="mensal", verbose_name="Período")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo", verbose_name="Status")
    unidade_medida = models.CharField(max_length=50, blank=True, null=True, verbose_name="Unidade de Medida")
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="indicadores_responsavel",
        verbose_name="Responsável",
    )
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="indicadores_criados",
        verbose_name="Criado por",
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Indicador"
        verbose_name_plural = "Indicadores"
        ordering = ["-data", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.data})"

    def get_absolute_url(self):
        return reverse("bi:bi_detail", args=[str(self.id)])

    def get_tipo_color(self):
        """Retorna a cor do tipo para uso nos templates"""
        colors = {
            "financeiro": "success",
            "produtividade": "primary",
            "qualidade": "info",
            "eficiencia": "warning",
            "vendas": "danger",
            "marketing": "purple",
            "operacional": "dark",
            "rh": "secondary",
            "outro": "light",
        }
        return colors.get(self.tipo, "primary")

    def get_status_color(self):
        """Retorna a cor do status para uso nos templates"""
        colors = {
            "ativo": "success",
            "inativo": "warning",
            "arquivado": "secondary",
        }
        return colors.get(self.status, "primary")

    def get_progresso_meta(self):
        """Calcula o progresso em relação à meta"""
        if self.meta and self.meta > 0:
            return round((self.valor / self.meta) * 100, 2)
        return 0

    def is_meta_atingida(self):
        """Verifica se a meta foi atingida"""
        if self.meta:
            return self.valor >= self.meta
        return False

    def get_valor_formatado(self):
        """Retorna o valor formatado com a unidade de medida"""
        if self.unidade_medida:
            return f"{self.valor} {self.unidade_medida}"
        return str(self.valor)

    def get_meta_formatada(self):
        """Retorna a meta formatada com a unidade de medida"""
        if self.meta:
            if self.unidade_medida:
                return f"{self.meta} {self.unidade_medida}"
            return str(self.meta)
        return "Não definida"

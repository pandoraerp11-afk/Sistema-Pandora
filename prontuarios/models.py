import contextlib

from django.db import models

from clientes.models import Cliente, PessoaFisica
from core.models import (  # Assumindo que core.models contém Tenant, CustomUser e TimestampedModel
    CustomUser,
    Tenant,
    TimestampedModel,
)
from servicos.models import Servico

# Choices necessários para PerfilClinico e demais modelos (antes definidos junto de Paciente)
SEXO_CHOICES = [
    ("M", "Masculino"),
    ("F", "Feminino"),
    ("O", "Outro"),
]

ESTADO_CIVIL_CHOICES = [
    ("SOLTEIRO", "Solteiro(a)"),
    ("CASADO", "Casado(a)"),
    ("DIVORCIADO", "Divorciado(a)"),
    ("VIUVO", "Viúvo(a)"),
    ("UNIAO_ESTAVEL", "União Estável"),
]

TIPO_SANGUINEO_CHOICES = [
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
]

TIPO_PELE_CHOICES = [
    ("NORMAL", "Normal"),
    ("SECA", "Seca"),
    ("OLEOSA", "Oleosa"),
    ("MISTA", "Mista"),
    ("SENSIVEL", "Sensível"),
]

FOTOTIPO_CHOICES = [
    ("I", "I - Branca (sensível)"),
    ("II", "II - Branca (pouco sensível)"),
    ("III", "III - Morena Clara (moderadamente sensível)"),
    ("IV", "IV - Morena Moderada (pouco sensível)"),
    ("V", "V - Morena Escura (resistente)"),
    ("VI", "VI - Negra (resistente)"),
]

"""Removido modelo Paciente: todas as referências clínicas agora vinculam direto a Cliente e/ou PerfilClinico."""


# === Novo Modelo: Perfil Clínico ligado ao Cliente (Pessoa Física) ===
class PerfilClinico(TimestampedModel):
    """Perfil clínico complementar para um Cliente PF.
    Mantém campos de saúde separados do cadastro comercial.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="perfils_clinicos")
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="perfil_clinico")
    pessoa_fisica = models.OneToOneField(
        PessoaFisica,
        on_delete=models.CASCADE,
        related_name="perfil_clinico",
        null=True,
        blank=True,
        help_text="Redundância leve para acesso rápido a atributos PF",
    )

    # Dados médicos básicos
    tipo_sanguineo = models.CharField(max_length=3, choices=TIPO_SANGUINEO_CHOICES, blank=True, null=True)
    alergias = models.TextField(blank=True, null=True)
    medicamentos_uso = models.TextField(blank=True, null=True)
    doencas_cronicas = models.TextField(blank=True, null=True)
    cirurgias_anteriores = models.TextField(blank=True, null=True)

    # Estética / dermatologia
    tipo_pele = models.CharField(max_length=20, choices=TIPO_PELE_CHOICES, blank=True, null=True)
    fototipo = models.CharField(max_length=10, choices=FOTOTIPO_CHOICES, blank=True, null=True)
    historico_estetico = models.TextField(blank=True, null=True)

    # Contato emergência
    contato_emergencia_nome = models.CharField(max_length=200, blank=True, null=True)
    contato_emergencia_telefone = models.CharField(max_length=20, blank=True, null=True)
    contato_emergencia_parentesco = models.CharField(max_length=50, blank=True, null=True)

    # Consentimentos e termos
    termo_responsabilidade_assinado = models.BooleanField(default=False)
    data_assinatura_termo = models.DateTimeField(blank=True, null=True)
    lgpd_consentimento = models.BooleanField(default=False)
    data_consentimento_lgpd = models.DateTimeField(blank=True, null=True)

    observacoes_gerais = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil Clínico"
        verbose_name_plural = "Perfis Clínicos"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "cliente"], name="unique_perfil_clinico_cliente_tenant")
        ]

    def __str__(self):
        return f"Perfil Clínico de {self.cliente.nome_display if self.cliente_id else '—'}"


# Modelo Procedimento removido – usar Servico + ServicoClinico (categoria via FK em servicos)


# Choices para Atendimento
STATUS_ATENDIMENTO_CHOICES = [
    ("AGENDADO", "Agendado"),
    ("EM_ANDAMENTO", "Em Andamento"),
    ("CONCLUIDO", "Concluído"),
    ("CANCELADO", "Cancelado"),
    ("REAGENDADO", "Reagendado"),
]

FORMA_PAGAMENTO_CHOICES = [
    ("DINHEIRO", "Dinheiro"),
    ("CARTAO_CREDITO", "Cartão de Crédito"),
    ("CARTAO_DEBITO", "Cartão de Débito"),
    ("PIX", "PIX"),
    ("TRANSFERENCIA", "Transferência Bancária"),
    ("OUTRO", "Outro"),
]


class Atendimento(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="atendimentos")
    # Cliente relacionado (substitui antigo paciente)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="atendimentos",
        help_text="Vínculo direto ao Cliente (antes Paciente)",
    )
    # Temporariamente opcional até limpeza completa de dados legados
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="atendimentos", null=True, blank=True)
    profissional = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="atendimentos_realizados")
    # Vínculo a Evento da agenda unificada (para notificações / calendários) - LEGADO
    evento_agenda = models.ForeignKey(
        "agenda.Evento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atendimentos_legados",
        help_text="LEGADO: Evento na agenda associado",
    )

    # Dados do atendimento
    data_atendimento = models.DateTimeField(verbose_name="Data e Hora do Atendimento")
    numero_sessao = models.PositiveIntegerField(verbose_name="Número da Sessão")
    status = models.CharField(max_length=20, choices=STATUS_ATENDIMENTO_CHOICES, default="AGENDADO")
    ORIGEM_AGENDAMENTO_CHOICES = [
        ("CLIENTE", "Cliente"),
        ("PROFISSIONAL", "Profissional"),
        ("SECRETARIA", "Secretaria"),
        ("SISTEMA", "Sistema"),
    ]
    origem_agendamento = models.CharField(max_length=20, choices=ORIGEM_AGENDAMENTO_CHOICES, default="PROFISSIONAL")

    # Avaliação pré-serviço (nomes de campos mantidos por compatibilidade)
    pressao_arterial = models.CharField(max_length=10, blank=True, null=True, verbose_name="Pressão Arterial")
    peso = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Peso (kg)")
    altura = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, verbose_name="Altura (m)")

    # Detalhes do serviço realizado (nomes de campos mantidos por compatibilidade)
    area_tratada = models.CharField(max_length=200, verbose_name="Área Tratada")
    equipamento_utilizado = models.CharField(max_length=200, blank=True, null=True)
    parametros_equipamento = models.JSONField(default=dict, blank=True, verbose_name="Parâmetros do Equipamento")
    produtos_utilizados = models.TextField(blank=True, null=True, verbose_name="Produtos Utilizados")

    # Observações e evolução
    observacoes_pre_procedimento = models.TextField(blank=True, null=True)
    observacoes_durante_procedimento = models.TextField(blank=True, null=True)
    observacoes_pos_procedimento = models.TextField(blank=True, null=True)
    reacoes_adversas = models.TextField(blank=True, null=True, verbose_name="Reações Adversas")

    # Avaliação de resultados
    satisfacao_cliente = models.PositiveIntegerField(
        choices=[(i, i) for i in range(1, 11)], blank=True, null=True, verbose_name="Satisfação do Cliente (1-10)"
    )
    avaliacao_profissional = models.TextField(blank=True, null=True, verbose_name="Avaliação do Profissional")

    # Dados financeiros
    valor_cobrado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Cobrado")
    desconto_aplicado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pagamento = models.CharField(max_length=50, choices=FORMA_PAGAMENTO_CHOICES)

    # Próxima sessão
    data_proxima_sessao = models.DateTimeField(blank=True, null=True, verbose_name="Data da Próxima Sessão")
    observacoes_proxima_sessao = models.TextField(blank=True, null=True)

    # Assinaturas digitais
    assinatura_cliente = models.TextField(blank=True, null=True, verbose_name="Assinatura Digital do Cliente")
    assinatura_profissional = models.TextField(blank=True, null=True, verbose_name="Assinatura Digital do Profissional")
    # Integração nova: vínculo opcional ao novo fluxo de agendamentos (fase migração)
    agendamento = models.ForeignKey(
        "agendamentos.Agendamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atendimentos_clinicos",
        help_text="Ligação ao novo Agendamento (beta)",
    )

    class Meta:
        verbose_name = "Atendimento"
        verbose_name_plural = "Atendimentos"

    def __str__(self):
        # Evita exceptions quando ainda não há FK resolvida (formulário de criação)
        proc_nome = "—"
        try:
            if getattr(self, "servico_id", None):
                proc_nome = getattr(getattr(self, "servico", None), "nome_servico", "—")
        except Exception:
            proc_nome = "—"

        cliente_nome = "—"
        try:
            if getattr(self, "cliente_id", None):
                cliente_nome = getattr(self.cliente, "nome_display", "—")
        except Exception:
            cliente_nome = "—"

        data_txt = "—"
        try:
            if getattr(self, "data_atendimento", None):
                data_txt = self.data_atendimento.strftime("%d/%m/%Y %H:%M")
        except Exception:
            data_txt = "—"

        return f"Atendimento {proc_nome} para {cliente_nome} em {data_txt}"


# === Modelos de Agendamento Legados (Removidos) ===
# Os modelos AtendimentoDisponibilidade e AtendimentoSlot foram removidos
# em favor do novo módulo 'agendamentos'. A lógica de disponibilidade,
# slots e reservas agora é centralizada em 'agendamentos.services'.


# Choices para FotoEvolucao
TIPO_FOTO_CHOICES = [
    ("ANTES", "Antes"),
    ("DURANTE", "Durante"),
    ("DEPOIS", "Depois"),
    ("GERAL", "Geral"),
]

MOMENTO_FOTO_CHOICES = [
    ("INICIO_TRATAMENTO", "Início do Tratamento"),
    ("MEIO_TRATAMENTO", "Meio do Tratamento"),
    ("FIM_TRATAMENTO", "Fim do Tratamento"),
    ("SESSAO_ESPECIFICA", "Sessão Específica"),
    ("ACOMPANHAMENTO", "Acompanhamento"),
]


class FotoEvolucao(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="fotos_evolucao")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="fotos_evolucao")
    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE, related_name="fotos", blank=True, null=True)

    # Dados da foto
    titulo = models.CharField(max_length=200, verbose_name="Título/Descrição")
    tipo_foto = models.CharField(max_length=20, choices=TIPO_FOTO_CHOICES, verbose_name="Tipo de Foto")
    momento = models.CharField(max_length=20, choices=MOMENTO_FOTO_CHOICES, verbose_name="Momento")
    area_fotografada = models.CharField(max_length=200, verbose_name="Área Fotografada")

    # Arquivo da imagem
    imagem = models.ImageField(upload_to="prontuarios/fotos_evolucao/", verbose_name="Imagem")
    imagem_thumbnail = models.ImageField(upload_to="prontuarios/thumbnails/", blank=True, null=True)
    imagem_webp = models.ImageField(
        upload_to="prontuarios/webp/", blank=True, null=True, help_text="Versão otimizada WEBP"
    )
    video = models.FileField(
        upload_to="prontuarios/videos_evolucao/", blank=True, null=True, help_text="Vídeo curto do serviço (opcional)"
    )
    video_poster = models.ImageField(
        upload_to="prontuarios/videos_posters/",
        blank=True,
        null=True,
        help_text="Frame de pré-visualização extraído do vídeo",
    )
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    video_meta = models.JSONField(
        blank=True, null=True, help_text="Metadados e status de validação/transcodificação do vídeo"
    )

    # Metadados
    data_foto = models.DateTimeField(verbose_name="Data da Foto")
    angulo_foto = models.CharField(max_length=50, blank=True, null=True, verbose_name="Ângulo da Foto")
    iluminacao = models.CharField(max_length=50, blank=True, null=True, verbose_name="Condições de Iluminação")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    # Configurações de privacidade
    visivel_cliente = models.BooleanField(default=True, verbose_name="Visível para o Cliente")
    uso_autorizado_marketing = models.BooleanField(default=False, verbose_name="Autorizado para Marketing")

    # Dados técnicos da imagem
    resolucao = models.CharField(max_length=20, blank=True, null=True)
    tamanho_arquivo = models.PositiveIntegerField(blank=True, null=True, verbose_name="Tamanho do Arquivo (bytes)")
    hash_arquivo = models.CharField(max_length=64, blank=True, null=True, verbose_name="Hash SHA-256")

    class Meta:
        verbose_name = "Foto de Evolução"
        verbose_name_plural = "Fotos de Evolução"
        indexes = [
            models.Index(fields=["tenant", "data_foto"]),
            models.Index(fields=["tenant", "cliente"]),
            # índice antigo por paciente removido
        ]

    def __str__(self):
        return f"Foto de {getattr(self.cliente, 'nome_display', '—')} - {self.titulo} ({self.data_foto.strftime('%d/%m/%Y')})"

    def save(self, *args, **kwargs):
        import hashlib

        # Calcular hash e tamanho se imagem nova
        if self.imagem and (not self.hash_arquivo or not self.tamanho_arquivo):
            try:
                self.imagem.seek(0)
                data = self.imagem.read()
                self.tamanho_arquivo = len(data)
                self.hash_arquivo = hashlib.sha256(data).hexdigest()
            except Exception:
                pass
            finally:
                with contextlib.suppress(Exception):
                    self.imagem.seek(0)
        # Capturar mime_type básico
        if self.imagem and not self.mime_type:
            with contextlib.suppress(Exception):
                self.mime_type = getattr(self.imagem.file, "content_type", None)
        if self.video and not self.mime_type:
            with contextlib.suppress(Exception):
                self.mime_type = getattr(self.video.file, "content_type", None)
        super().save(*args, **kwargs)
        # Disparar geração assíncrona de derivados (thumbnail, webp, poster)
        if self.imagem or self.video:
            try:
                from .tasks import (
                    extrair_video_poster,
                    gerar_thumbnail_foto,
                    gerar_variacao_webp,
                    transcodificar_video,
                    validar_video,
                )

                if self.imagem:
                    gerar_thumbnail_foto.delay(self.id)
                    gerar_variacao_webp.delay(self.id)
                if self.video:
                    # Validação sempre primeiro
                    validar_video.delay(self.id)
                    if not self.video_poster:
                        extrair_video_poster.delay(self.id)
                    # Tentativa de transcodificação h264 (pode ser fila futura)
                    transcodificar_video.apply_async([self.id, "h264"], countdown=10)
            except Exception:
                pass

    def clean(self):
        from django.core.exceptions import ValidationError

        max_image_mb = 8
        max_video_mb = 50
        if self.imagem and self.imagem.size > max_image_mb * 1024 * 1024:
            raise ValidationError({"imagem": f"Imagem excede {max_image_mb}MB"})
        if self.video and self.video.size > max_video_mb * 1024 * 1024:
            raise ValidationError({"video": f"Vídeo excede {max_video_mb}MB"})
        # Validar extensões simples
        import os

        if self.video:
            ext = os.path.splitext(self.video.name)[1].lower()
            if ext not in [".mp4", ".mov", ".m4v", ".webm"]:
                raise ValidationError({"video": "Formato de vídeo não suportado"})


# Choices para Anamnese
TIPO_ANAMNESE_CHOICES = [
    ("GERAL", "Anamnese Geral"),
    ("FACIAL", "Anamnese Facial"),
    ("CORPORAL", "Anamnese Corporal"),
    ("CAPILAR", "Anamnese Capilar"),
    ("LASER", "Anamnese Laser"),
    ("INJETAVEIS", "Anamnese Injetáveis"),
]

STATUS_ANAMNESE_CHOICES = [
    ("PREENCHIDA", "Preenchida"),
    ("EM_REVISAO", "Em Revisão"),
    ("APROVADA", "Aprovada"),
    ("REJEITADA", "Rejeitada"),
]


class Anamnese(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="anamneses")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="anamneses")
    # Temporariamente opcional (será tornado obrigatório após garantir migração completa)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="anamneses", null=True, blank=True)
    atendimento = models.ForeignKey(
        Atendimento, on_delete=models.CASCADE, related_name="anamneses", blank=True, null=True
    )

    # Dados da anamnese
    tipo_anamnese = models.CharField(max_length=50, choices=TIPO_ANAMNESE_CHOICES)
    data_preenchimento = models.DateTimeField(auto_now_add=True)
    profissional_responsavel = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="anamneses_supervisionadas"
    )

    # Respostas (JSON flexível para diferentes tipos de anamnese)
    respostas = models.JSONField(default=dict, verbose_name="Respostas da Anamnese")

    # Avaliação profissional
    observacoes_profissional = models.TextField(blank=True, null=True)
    contraindicacoes_identificadas = models.TextField(blank=True, null=True)
    recomendacoes = models.TextField(blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_ANAMNESE_CHOICES, default="PREENCHIDA")
    aprovada_por = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="anamneses_aprovadas"
    )
    data_aprovacao = models.DateTimeField(blank=True, null=True)

    # Assinatura digital
    assinatura_cliente = models.TextField(blank=True, null=True)
    assinatura_profissional = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Anamnese"
        verbose_name_plural = "Anamneses"

    def __str__(self):
        return f"Anamnese de {getattr(self.cliente, 'nome_display', '—')} para {self.servico.nome_servico} ({self.get_tipo_anamnese_display()})"

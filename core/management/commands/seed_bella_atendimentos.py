import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from agendamentos.models import Agendamento
from clientes.models import Cliente
from core.models import Tenant
from prontuarios.models import Atendimento, PerfilClinico


class Command(BaseCommand):
    help = "Cria Atendimentos e Perfis Clínicos para agendamentos existentes da Bella Estética"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, default="bella", help="Subdomain do tenant (padrão: bella)")
        parser.add_argument("--limpar", action="store_true", help="Remove atendimentos e perfis clínicos anteriores")
        parser.add_argument("--quiet", action="store_true", help="Modo silencioso")

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        tenant_subdomain = options["tenant"]

        if not quiet:
            self.stdout.write(self.style.NOTICE(f"=== Seed Atendimentos/Perfis Clínicos - {tenant_subdomain} ==="))

        try:
            tenant = Tenant.objects.get(subdomain=tenant_subdomain)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant "{tenant_subdomain}" não encontrado.'))
            return

        if options["limpar"]:
            Atendimento.objects.filter(tenant=tenant).delete()
            PerfilClinico.objects.filter(tenant=tenant).delete()
            if not quiet:
                self.stdout.write("Atendimentos e perfis clínicos removidos.")

        # --- Perfis Clínicos para Clientes PF ---
        clientes_pf = Cliente.objects.filter(tenant=tenant, tipo="PF").select_related("pessoafisica")
        perfis_criados = 0

        for cliente in clientes_pf:
            if not hasattr(cliente, "perfil_clinico"):
                PerfilClinico.objects.create(
                    tenant=tenant,
                    cliente=cliente,
                    pessoa_fisica=getattr(cliente, "pessoafisica", None),
                    tipo_sanguineo=random.choice(["A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"]),
                    tipo_pele=random.choice(["NORMAL", "SECA", "OLEOSA", "MISTA", "SENSIVEL"]),
                    fototipo=random.choice(["II", "III", "IV", "V"]),
                    alergias="Nenhuma alergia conhecida."
                    if random.choice([True, False])
                    else "Alergia a produtos com ácido salicílico.",
                    termo_responsabilidade_assinado=True,
                    data_assinatura_termo=timezone.now(),
                    lgpd_consentimento=True,
                    data_consentimento_lgpd=timezone.now(),
                    observacoes_gerais=f"Perfil clínico criado automaticamente para {cliente.nome_display}",
                )
                perfis_criados += 1

        if not quiet:
            self.stdout.write(f"Perfis clínicos criados: {perfis_criados}")

        # --- Atendimentos para Agendamentos CONFIRMADOS ---
        agendamentos_confirmados = (
            Agendamento.objects.filter(tenant=tenant, status="CONFIRMADO")
            .select_related("cliente", "profissional", "servico")
            .order_by("data_inicio")
        )

        atendimentos_criados = 0
        valores_base = {
            "Limpeza de Pele Profunda": 180.00,
            "Peeling Químico Suave": 250.00,
            "Drenagem Linfática Corporal": 150.00,
            "Massagem Relaxante": 140.00,
            "Depilação a Laser Axilas": 220.00,
            "Harmonização Facial (avaliação)": 300.00,
        }

        for agendamento in agendamentos_confirmados:
            # Só criar se ainda não existe atendimento vinculado
            if not hasattr(agendamento, "atendimentos_clinicos") or agendamento.atendimentos_clinicos.count() == 0:
                valor_base = valores_base.get(
                    getattr(getattr(agendamento, "servico", None), "nome_servico", "Serviço"), 200.00
                )
                desconto = random.choice([0, 10, 20, 50]) if random.choice([True, False, False, False]) else 0
                valor_final = valor_base - desconto

                # Simular se já foi realizado (70% dos confirmados já foram feitos)
                foi_realizado = random.choice([True, True, True, False])
                status_atendimento = "CONCLUIDO" if foi_realizado else "AGENDADO"

                Atendimento.objects.create(
                    tenant=tenant,
                    cliente=agendamento.cliente,
                    servico=agendamento.servico,
                    profissional=agendamento.profissional,
                    agendamento=agendamento,  # VÍNCULO PRINCIPAL
                    data_atendimento=agendamento.data_inicio,
                    numero_sessao=1,
                    status=status_atendimento,
                    origem_agendamento="OPERADOR",
                    # Dados simulados
                    area_tratada=self._get_area_tratada(
                        getattr(getattr(agendamento, "servico", None), "nome_servico", "Serviço")
                    ),
                    equipamento_utilizado=self._get_equipamento(
                        getattr(getattr(agendamento, "servico", None), "categoria", None)
                    ),
                    produtos_utilizados=self._get_produtos(
                        getattr(getattr(agendamento, "servico", None), "categoria", None)
                    ),
                    # Financeiro
                    valor_cobrado=valor_final,
                    desconto_aplicado=desconto,
                    forma_pagamento=random.choice(["PIX", "CARTAO_CREDITO", "CARTAO_DEBITO", "DINHEIRO"]),
                    # Observações simuladas se foi concluído
                    observacoes_pre_procedimento="Cliente chegou pontualmente." if foi_realizado else "",
                    observacoes_durante_procedimento="Procedimento transcorreu normalmente." if foi_realizado else "",
                    observacoes_pos_procedimento="Cliente satisfeita com resultado." if foi_realizado else "",
                    satisfacao_cliente=random.randint(8, 10) if foi_realizado else None,
                    # Próxima sessão (se aplicável)
                    data_proxima_sessao=agendamento.data_inicio + timedelta(days=random.randint(15, 45))
                    if random.choice([True, False])
                    else None,
                )
                atendimentos_criados += 1

        if not quiet:
            self.stdout.write(f"Atendimentos criados: {atendimentos_criados}")
            self.stdout.write(self.style.SUCCESS("Seed de atendimentos/perfis concluído."))

    def _get_area_tratada(self, procedimento_nome):
        mapa = {
            "Limpeza de Pele Profunda": "Face completa",
            "Peeling Químico Suave": "Face - região T e bochechas",
            "Drenagem Linfática Corporal": "Membros inferiores e abdomen",
            "Massagem Relaxante": "Costas, pescoço e ombros",
            "Depilação a Laser Axilas": "Axilas bilaterais",
            "Harmonização Facial (avaliação)": "Avaliação facial completa",
        }
        return mapa.get(procedimento_nome, "Área não especificada")

    def _get_equipamento(self, categoria):
        equipamentos = {
            "FACIAL": ["Microdermoabrasão", "Vapor de ozônio", "Alta frequência"],
            "CORPORAL": ["Endermologia", "Pressoterapia", "Drenador"],
            "LASER": ["Laser Alexandrite", "Laser Diodo", "IPL"],
            "INJETAVEIS": ["Não aplicável - avaliação"],
        }
        opcoes = equipamentos.get(categoria, ["Equipamento padrão"])
        return random.choice(opcoes)

    def _get_produtos(self, categoria):
        produtos = {
            "FACIAL": "Sabonete facial, tônico, hidratante pós-procedimento",
            "CORPORAL": "Óleo de drenagem, creme firmador",
            "LASER": "Gel condutor, protetor solar FPS 60",
            "INJETAVEIS": "Não aplicável",
        }
        return produtos.get(categoria, "Produtos básicos de higienização")

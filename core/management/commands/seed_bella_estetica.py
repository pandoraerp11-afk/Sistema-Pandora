import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from agendamentos.models import Agendamento, Disponibilidade, Slot
from clientes.models import Cliente, PessoaFisica
from core.models import CustomUser, Department, Tenant, TenantUser
from funcionarios.models import Funcionario
from servicos.models import Servico, ServicoClinico


class Command(BaseCommand):
    help = "Popula dados de exemplo para a clínica 'Bella Estética' (profissionais, procedimentos, clientes, agendamentos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove dados anteriores relacionados ao tenant Bella Estetica antes de recriar.",
        )
        parser.add_argument(
            "--dias", type=int, default=5, help="Dias futuros de agenda para gerar slots e agendamentos."
        )
        parser.add_argument("--quiet", action="store_true", help="Modo silencioso.")

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        dias = options["dias"]
        if not quiet:
            self.stdout.write(self.style.NOTICE("== Seed Bella Estética =="))

        tenant, created = Tenant.objects.get_or_create(
            subdomain="bella", defaults={"name": "Bella Estética", "status": "active", "tipo_pessoa": "PJ"}
        )
        if not quiet:
            self.stdout.write(("Criado" if created else "Usando") + f" tenant: {tenant.name} (id={tenant.id})")

        if options["limpar"]:
            # Remove dados dependentes (ordem inversa)
            Agendamento.objects.filter(tenant=tenant).delete()
            Slot.objects.filter(tenant=tenant).delete()
            Disponibilidade.objects.filter(tenant=tenant).delete()
            Servico.objects.filter(tenant=tenant).delete()
            Cliente.objects.filter(tenant=tenant).delete()
            Funcionario.objects.filter(tenant=tenant).delete()
            # Profissionais ficam para não perder usuários já existentes
            if not quiet:
                self.stdout.write(
                    "Dados antigos removidos (funcionários, procedimentos, clientes, agendamentos, slots)."
                )

        # --- Departamento ---
        dept_estetica, _ = Department.objects.get_or_create(
            tenant=tenant, name="Estética", defaults={"description": "Departamento de Estética e Beleza"}
        )

        # --- Profissionais (Funcionários + Usuários) ---
        profissionais_spec = [
            ("estetica.ana", "Ana Silva Santos", "Esteticista Facial"),
            ("estetica.julia", "Júlia Ramos Oliveira", "Esteticista Corporal"),
            ("estetica.marina", "Marina Lopes Costa", "Esteticista Laser"),
        ]
        profissionais = []
        funcionarios = []
        for username, nome_completo, cargo in profissionais_spec:
            # Criar usuário
            user, _ = CustomUser.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome_completo.split()[0],
                    "last_name": " ".join(nome_completo.split()[1:]) or "Prof",
                    "email": f"{username}@bellaestetica.com",
                },
            )
            profissionais.append(user)
            TenantUser.objects.get_or_create(tenant=tenant, user=user, defaults={"is_tenant_admin": False})

            # Criar funcionário
            cpf_fake = f"{random.randint(100, 999)}.{random.randint(100, 999)}.{random.randint(100, 999)}-{random.randint(10, 99)}"
            funcionario, _ = Funcionario.objects.get_or_create(
                tenant=tenant,
                cpf=cpf_fake,
                defaults={
                    "user": user,
                    "nome_completo": nome_completo,
                    "data_nascimento": date(1990 + random.randint(0, 15), random.randint(1, 12), random.randint(1, 28)),
                    "sexo": "F",
                    "data_admissao": date(2020 + random.randint(0, 4), random.randint(1, 12), random.randint(1, 28)),
                    "cargo": cargo,
                    "departamento": dept_estetica,
                    "tipo_contrato": "CLT",
                    "salario_base": 3500.00 + random.randint(0, 2000),
                    "email_pessoal": f"{nome_completo.split()[0].lower()}@gmail.com",
                    "telefone_pessoal": f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
                    "escolaridade": "SUPERIOR_COMPLETO",
                    "profissao": cargo,
                    "ativo": True,
                },
            )
            funcionarios.append(funcionario)
        if not quiet:
            self.stdout.write(f"Funcionários/Profissionais: {len(funcionarios)}")

        # --- Serviços Clínicos ---
        servicos_spec = [
            (
                "Limpeza de Pele Profunda",
                "FACIAL",
                "Limpeza completa com hidratação e extração de impurezas.",
                60,
                180.00,
            ),
            ("Peeling Químico Suave", "FACIAL", "Peeling para renovação celular superficial.", 45, 250.00),
            (
                "Drenagem Linfática Corporal",
                "CORPORAL",
                "Terapia manual para estimular o sistema linfático.",
                50,
                150.00,
            ),
            ("Massagem Relaxante", "CORPORAL", "Massagem para alívio de tensão muscular e estresse.", 50, 140.00),
            ("Depilação a Laser Axilas", "LASER", "Sessão de depilação definitiva axilas.", 30, 220.00),
            (
                "Harmonização Facial (avaliação)",
                "INJETAVEIS",
                "Consulta inicial para avaliação de harmonização facial.",
                40,
                300.00,
            ),
        ]
        servicos = []
        for nome, _categoria, descricao, minutos, _valor in servicos_spec:
            serv, _ = Servico.objects.get_or_create(
                tenant=tenant,
                nome=nome,
                defaults={
                    "descricao": descricao,
                    "ativo": True,
                    "is_clinical": True,
                },
            )
            # perfil clínico
            ServicoClinico.objects.get_or_create(
                servico=serv,
                defaults={
                    "duracao_estimada": timedelta(minutes=minutos),
                    "requisitos_pre_procedimento": "",
                    "contraindicacoes": "",
                    "cuidados_pos_procedimento": "",
                    "requer_anamnese": False,
                    "requer_termo_consentimento": False,
                    "permite_fotos_evolucao": True,
                    "intervalo_minimo_sessoes": 0,
                },
            )
            servicos.append(serv)
        if not quiet:
            self.stdout.write(f"Serviços clínicos: {len(servicos)}")

        # --- Clientes (Pessoa Física) ---
        clientes_spec = [
            ("alice", "Alice Ferreira"),
            ("bruna", "Bruna Costa"),
            ("carla", "Carla Mendes"),
            ("diana", "Diana Souza"),
            ("elaine", "Elaine Martins"),
        ]
        clientes = []
        for cod, nome in clientes_spec:
            cliente, _ = Cliente.objects.get_or_create(
                tenant=tenant,
                codigo_interno=cod,
                defaults={"tipo": "PF", "status": "active", "email": f"{cod}@clientes.dev"},
            )
            # Pessoa física associada
            if not hasattr(cliente, "pessoafisica"):
                PessoaFisica.objects.create(
                    cliente=cliente,
                    nome_completo=nome,
                    cpf=f"{random.randint(100, 999)}.{random.randint(100, 999)}.{random.randint(100, 999)}-0{random.randint(0, 9)}",
                )
            clientes.append(cliente)
        if not quiet:
            self.stdout.write(f"Clientes: {len(clientes)}")

        # --- Disponibilidades e Slots ---
        hoje = timezone.localdate()
        slots_por_dia = []
        for profissional in profissionais:
            for d in range(dias):
                data = hoje + timedelta(days=d)
                # janela 09:00 - 17:00
                dispon, _ = Disponibilidade.objects.get_or_create(
                    tenant=tenant,
                    profissional=profissional,
                    data=data,
                    hora_inicio=time(9, 0),
                    hora_fim=time(17, 0),
                    defaults={"duracao_slot_minutos": 30},
                )
                # gerar slots a cada 60 min (simplificando)
                inicio_dt = timezone.make_aware(datetime.combine(data, time(9, 0)))
                for i in range(0, 8):  # 8 blocos de 60 min
                    horario = inicio_dt + timedelta(hours=i)
                    slot, _ = Slot.objects.get_or_create(
                        tenant=tenant,
                        disponibilidade=dispon,
                        profissional=profissional,
                        horario=horario,
                        defaults={"capacidade_total": 1},
                    )
                    slots_por_dia.append(slot)
        if not quiet:
            self.stdout.write(f"Slots criados/obtidos: {len(slots_por_dia)}")

        # --- Agendamentos ---
        agendamentos_criados = 0
        if not servicos:
            if not quiet:
                self.stdout.write(self.style.WARNING("Nenhum serviço criado – pulando criação de agendamentos."))
        elif not clientes:
            if not quiet:
                self.stdout.write(self.style.WARNING("Nenhum cliente criado – pulando criação de agendamentos."))
        elif not slots_por_dia:
            if not quiet:
                self.stdout.write(self.style.WARNING("Nenhum slot disponível – pulando criação de agendamentos."))
        else:
            random.seed(42)
            sample_slots = random.sample(slots_por_dia, min(25, len(slots_por_dia)))
            for slot in sample_slots:
                try:
                    # Segurança: garantir atributos mínimos
                    if not hasattr(slot, "disponivel"):
                        if not quiet:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Slot id={slot.id} sem propriedade disponivel (modelo alterado?). Pulando."
                                )
                            )
                        continue
                    if not slot.disponivel:
                        continue
                    if not slot.profissional_id:
                        continue
                    cliente = random.choice(clientes)
                    profissional = slot.profissional
                    serv = random.choice(servicos)
                    inicio = slot.horario
                    dur = getattr(serv.perfil_clinico, "duracao_estimada", timedelta(minutes=30))
                    fim = inicio + dur
                    ag, created_ag = Agendamento.objects.get_or_create(
                        tenant=tenant,
                        cliente=cliente,
                        profissional=profissional,
                        data_inicio=inicio,
                        defaults={
                            "data_fim": fim,
                            "status": "CONFIRMADO",
                            "origem": "OPERADOR",
                            "servico": serv,
                            "slot": slot,
                        },
                    )
                    if created_ag:
                        agendamentos_criados += 1
                except Exception as e:  # Log não aborta transação inteira
                    if not quiet:
                        self.stdout.write(
                            self.style.WARNING(f"Falha ao criar agendamento para slot {getattr(slot, 'id', '?')}: {e}")
                        )
            if not quiet:
                self.stdout.write(f"Agendamentos novos: {agendamentos_criados}")

        if not quiet:
            self.stdout.write(self.style.SUCCESS("Seed Bella Estética concluído."))

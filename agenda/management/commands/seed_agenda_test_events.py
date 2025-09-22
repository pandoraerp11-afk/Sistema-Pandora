from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from agenda.models import AgendaConfiguracao, Evento, EventoLembrete
from core.models import CustomUser, Tenant


class Command(BaseCommand):
    help = "Cria eventos de teste na Agenda com responsáveis, participantes e lembretes."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, help="ID do tenant para criar os eventos")
        parser.add_argument("--users", type=int, default=3, help="Qtde de usuários a usar (default 3)")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        users_qty = max(1, options.get("users") or 3)

        tenant = None
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Tenant {tenant_id} não encontrado"))
                return
        else:
            tenant = Tenant.objects.order_by("id").first()
            if not tenant:
                self.stdout.write(self.style.ERROR("Nenhum tenant encontrado"))
                return

        # Garantir configuração de Agenda
        AgendaConfiguracao.objects.get_or_create(tenant=tenant, defaults={"lembretes_padrao": [1440, 120, 15]})

        # Selecionar usuários do tenant (via memberships)
        users_qs = CustomUser.objects.filter(tenant_memberships__tenant=tenant).distinct()
        if users_qs.count() < users_qty:
            # fallback: usa quaisquer usuários do sistema
            users_qs = CustomUser.objects.all()

        users = list(users_qs[:users_qty])
        if not users:
            self.stdout.write(self.style.ERROR("Nenhum usuário disponível"))
            return

        # Montagem
        now = timezone.now()
        created = []

        def add_event(**kwargs):
            ev = Evento.objects.create(**kwargs)
            # Lembretes padrão 15 e 60 min para todos envolvidos
            uids = set()
            if ev.responsavel_id:
                uids.add(ev.responsavel_id)
            uids.update(list(ev.participantes.values_list("id", flat=True)))
            for uid in uids:
                EventoLembrete.objects.get_or_create(
                    evento=ev, usuario_id=uid, minutos_antes=15, defaults={"ativo": True}
                )
                EventoLembrete.objects.get_or_create(
                    evento=ev, usuario_id=uid, minutos_antes=60, defaults={"ativo": True}
                )
            return ev

        resp = users[0]
        parts = users[1:]

        # Evento 1 - hoje, em 30min (dura 1h) - pendente, alta, com participantes
        e1 = add_event(
            tenant=tenant,
            titulo="Reunião de Planejamento",
            descricao="Planejamento semanal da equipe",
            data_inicio=now + timedelta(minutes=30),
            data_fim=now + timedelta(minutes=90),
            dia_inteiro=False,
            status="pendente",
            prioridade="alta",
            local="Sala 1",
            tipo_evento="empresa",
            responsavel=resp,
        )
        if parts:
            e1.participantes.add(*parts)

        # Evento 2 - overlap com e1 (gera conflito após update)
        e2 = add_event(
            tenant=tenant,
            titulo="Call com Cliente X",
            descricao="Alinhamento de escopo",
            data_inicio=now + timedelta(minutes=60),
            data_fim=now + timedelta(minutes=120),
            dia_inteiro=False,
            status="pendente",
            prioridade="media",
            local="Google Meet",
            tipo_evento="cliente",
            responsavel=resp,
        )
        if parts:
            e2.participantes.add(parts[0])

        # Evento 3 - amanhã 10h às 11h, confirmado
        e3_start = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        e3 = add_event(
            tenant=tenant,
            titulo="Treinamento Interno",
            descricao="Treinamento de novas features",
            data_inicio=e3_start,
            data_fim=e3_start + timedelta(hours=1),
            dia_inteiro=False,
            status="confirmado",
            prioridade="baixa",
            local="Sala 2",
            tipo_evento="funcionario",
            responsavel=parts[0] if parts else resp,
        )
        if parts:
            e3.participantes.add(resp)

        # Evento 4 - hoje +3h às +4h
        e4 = add_event(
            tenant=tenant,
            titulo="Revisão de Código",
            descricao="Revisão Sprint",
            data_inicio=now + timedelta(hours=3),
            data_fim=now + timedelta(hours=4),
            dia_inteiro=False,
            status="pendente",
            prioridade="media",
            local="Sala 3",
            tipo_evento="outro",
            responsavel=resp,
        )

        created = [e1.id, e2.id, e3.id, e4.id]

        # Simula mudança de status e horário para disparar sinais de update/conflito
        e2.status = "confirmado"
        e2.data_inicio = now + timedelta(minutes=50)
        e2.save()

        self.stdout.write(self.style.SUCCESS(f"Eventos criados (tenant {tenant.id}): {created}"))

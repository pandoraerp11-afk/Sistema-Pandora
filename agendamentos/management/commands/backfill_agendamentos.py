from django.core.management.base import BaseCommand
from django.db import transaction

from agendamentos.models import Agendamento, Slot
from agendamentos.models_mapping import SlotLegacyMap
from prontuarios.models import Atendimento, AtendimentoSlot


class Command(BaseCommand):
    help = "Backfill: cria registros de Agendamento para atendimentos existentes que ainda não possuem vínculo (beta)."

    def add_arguments(self, parser):
        # Parâmetros de controle do backfill
        parser.add_argument("--limit", type=int, default=500, help="Máximo de atendimentos a processar por execução")
        parser.add_argument("--dry-run", action="store_true", help="Não persiste alterações, apenas simula")
        parser.add_argument(
            "--seed-perms", action="store_true", help="Também cria grupos e permissões padrão do módulo"
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        dry = options["dry_run"]
        qs = Atendimento.objects.filter(agendamento__isnull=True).order_by("id")[:limit]
        if options["seed_perms"]:
            self._seed_permissions()
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nada a backfill."))
            return
        created = 0
        for at in qs:
            with transaction.atomic():
                slot = None
                if at.slot_id:
                    legacy_slot: AtendimentoSlot = at.slot
                    # Tenta localizar mapeamento existente
                    map_obj = getattr(legacy_slot, "map_novo_slot", None)
                    if map_obj:
                        slot = map_obj.novo_slot
                    else:
                        # Criar disponibilidade e slot espelhado rápido
                        disp = None
                        if legacy_slot.disponibilidade_id:
                            ld = legacy_slot.disponibilidade
                            from agendamentos.models import Disponibilidade

                            disp = Disponibilidade.objects.filter(
                                tenant=ld.tenant,
                                profissional=ld.profissional,
                                data=ld.data,
                                hora_inicio=ld.hora_inicio,
                                hora_fim=ld.hora_fim,
                            ).first()
                            if not disp and not dry:
                                disp = Disponibilidade.objects.create(
                                    tenant=ld.tenant,
                                    profissional=ld.profissional,
                                    data=ld.data,
                                    hora_inicio=ld.hora_inicio,
                                    hora_fim=ld.hora_fim,
                                    duracao_slot_minutos=ld.duracao_slot_minutos,
                                    capacidade_por_slot=ld.capacidade_por_slot,
                                    recorrente=ld.recorrente,
                                    regra_recorrencia=ld.regra_recorrencia,
                                    ativo=ld.ativo,
                                )
                        if not slot:
                            # Garantir disponibilidade placeholder se não encontrada
                            if not disp and not dry:
                                disp = Disponibilidade.objects.create(
                                    tenant=legacy_slot.tenant,
                                    profissional=legacy_slot.profissional,
                                    data=legacy_slot.horario.date(),
                                    hora_inicio=legacy_slot.horario.time(),
                                    hora_fim=legacy_slot.horario.time(),
                                    duracao_slot_minutos=30,
                                    capacidade_por_slot=legacy_slot.capacidade_total,
                                    recorrente=False,
                                    ativo=True,
                                )
                            if not dry:
                                slot = Slot.objects.create(
                                    tenant=legacy_slot.tenant,
                                    disponibilidade=disp,
                                    profissional=legacy_slot.profissional,
                                    horario=legacy_slot.horario,
                                    capacidade_total=legacy_slot.capacidade_total,
                                    capacidade_utilizada=min(
                                        legacy_slot.capacidade_utilizada, legacy_slot.capacidade_total
                                    ),
                                    ativo=legacy_slot.ativo,
                                )
                            else:
                                slot = None
                        if slot and not dry:
                            SlotLegacyMap.objects.create(tenant=at.tenant, legacy_slot=legacy_slot, novo_slot=slot)
                # Calcular data_fim usando duração do serviço, se disponível
                data_inicio = at.data_atendimento
                data_fim = at.data_atendimento
                try:
                    dur = getattr(
                        getattr(getattr(at, "servico", None), "perfil_clinico", None), "duracao_estimada", None
                    )
                    if dur:
                        data_fim = data_inicio + dur
                except Exception:
                    pass
                ag = Agendamento(
                    tenant=at.tenant,
                    cliente=at.cliente,
                    profissional=at.profissional,
                    slot=slot,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    origem="PROFISSIONAL",
                    # tipo_servico removido
                    metadata={"backfill": True, "atendimento_id": at.id},
                    status="CONFIRMADO",
                )
                if not dry:
                    ag.save()
                    at.agendamento = ag
                    at.save(update_fields=["agendamento"])
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Backfill concluído: {created} agendamentos criados (dry_run={dry})."))

    def _seed_permissions(self):
        from django.contrib.auth.models import Group, Permission

        modelos = ["agendamento", "disponibilidade", "slot", "auditoriaagendamento"]
        grupos = {
            "AGENDAMENTOS_SECRETARIA": ["view", "add", "change", "delete"],
            "AGENDAMENTOS_PROFISSIONAL": ["view"],
        }
        for group_name, actions in grupos.items():
            g, _ = Group.objects.get_or_create(name=group_name)
            perms_ids = []
            for model in modelos:
                for act in actions:
                    codename = f"{act}_{model}"
                    perm = Permission.objects.filter(codename=codename).first()
                    if perm:
                        g.permissions.add(perm)
                        perms_ids.append(perm.id)
            g.save()
        self.stdout.write(self.style.SUCCESS("Permissões/Grupos de agendamentos seed criados/atualizados."))

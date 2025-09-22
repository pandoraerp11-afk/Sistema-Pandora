from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria ou atualiza grupos e permissões padrão do módulo de agendamentos."

    def handle(self, *args, **options):
        from django.contrib.auth.models import Group, Permission

        modelos = ["agendamento", "disponibilidade", "slot", "auditoriaagendamento"]
        grupos = {
            # Secretaria: acesso total no módulo
            "AGENDAMENTOS_SECRETARIA": ["view", "add", "change", "delete"],
            # Profissional (legado): leitura via API conforme permission class
            "AGENDAMENTOS_PROFISSIONAL": ["view"],
            # Visualização global somente leitura (SAFE_METHODS) — grupo novo
            "AGENDAMENTOS_VISUALIZAR": ["view"],
        }
        for group_name, actions in grupos.items():
            g, _ = Group.objects.get_or_create(name=group_name)
            for model in modelos:
                for act in actions:
                    perm = Permission.objects.filter(codename=f"{act}_{model}").first()
                    if perm:
                        g.permissions.add(perm)
            g.save()
        self.stdout.write(self.style.SUCCESS("Permissões e grupos de agendamentos configurados."))

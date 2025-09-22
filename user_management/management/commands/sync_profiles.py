from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from user_management.models import StatusUsuario
from user_management.services.profile_service import ensure_profile

User = get_user_model()


class Command(BaseCommand):
    help = "Sincroniza (idempotente) perfis estendidos: garante criação, ajusta status conforme user.is_active e reporta discrepâncias."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Mostra ações sem persistir alterações de status.")
        parser.add_argument("--verbose", action="store_true", help="Lista cada usuário processado.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        verbose = options["verbose"]

        total_users = User.objects.count()
        self.stdout.write(f"Total de usuários: {total_users}")

        created = 0
        status_fixed = 0
        inconsistencias = []

        for user in User.objects.all().iterator():
            perfil = getattr(user, "perfil_estendido", None)
            if not perfil:
                if dry:
                    created += 1
                    if verbose:
                        self.stdout.write(f"[DRY] Criaria perfil para {user.username}")
                else:
                    ensure_profile(user)
                    created += 1
                    if verbose:
                        self.stdout.write(f"[OK] Perfil criado para {user.username}")
                perfil = getattr(user, "perfil_estendido", None)
            # Verificar consistência de status
            if perfil:
                esperado = StatusUsuario.ATIVO if user.is_active else StatusUsuario.INATIVO
                if perfil.status != esperado:
                    inconsistencias.append((user.username, perfil.status, esperado))
                    if not dry:
                        perfil.status = esperado
                        perfil.save(update_fields=["status"])
                        status_fixed += 1
                        if verbose:
                            self.stdout.write(f"[FIX] Ajustado status {user.username}: {perfil.status} -> {esperado}")
                    elif verbose:
                        self.stdout.write(f"[DRY] Ajustaria status {user.username}: {perfil.status} -> {esperado}")
        # Resumo
        self.stdout.write("=== Resumo Sync Profiles ===")
        self.stdout.write(f"Perfis criados: {created}")
        self.stdout.write(f"Status corrigidos: {status_fixed}{' (dry-run)' if dry else ''}")
        self.stdout.write(f"Inconsistências detectadas: {len(inconsistencias)}")
        if inconsistencias and not verbose:
            for u, atual, exp in inconsistencias[:10]:
                self.stdout.write(f" - {u}: {atual} -> {exp}")
            if len(inconsistencias) > 10:
                self.stdout.write(f"   ... (+{len(inconsistencias) - 10} outras)")
        self.stdout.write(self.style.SUCCESS("Sincronização concluída."))

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from user_management.models import PerfilUsuarioEstendido

User = get_user_model()


class Command(BaseCommand):
    help = "Cria perfis estendidos para todos os usuários que não possuem"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas simula a execução sem fazer alterações no banco",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("=== Verificando perfis estendidos ===")

        total_users = User.objects.count()
        total_perfis = PerfilUsuarioEstendido.objects.count()

        self.stdout.write(f"Total de usuários: {total_users}")
        self.stdout.write(f"Total de perfis estendidos: {total_perfis}")

        # Encontrar usuários sem perfil
        usuarios_sem_perfil = []
        for user in User.objects.all():
            if not PerfilUsuarioEstendido.objects.filter(user=user).exists():
                usuarios_sem_perfil.append(user)

        if not usuarios_sem_perfil:
            self.stdout.write(self.style.SUCCESS("✓ Todos os usuários já possuem perfis estendidos"))
            return

        self.stdout.write(f"Usuários sem perfil estendido: {len(usuarios_sem_perfil)}")

        if dry_run:
            self.stdout.write("\n=== SIMULAÇÃO (dry-run) ===")
            for user in usuarios_sem_perfil:
                self.stdout.write(f"Seria criado perfil para: {user.username}")
            self.stdout.write(f"\nTotal de perfis que seriam criados: {len(usuarios_sem_perfil)}")
            return

        # Criar perfis faltantes
        self.stdout.write("\n=== Criando perfis ===")
        perfis_criados = 0

        for user in usuarios_sem_perfil:
            try:
                perfil, created = PerfilUsuarioEstendido.objects.get_or_create(user=user)
                if created:
                    perfis_criados += 1
                    self.stdout.write(f"✓ Criado perfil para: {user.username}")
                else:
                    self.stdout.write(f"- Perfil já existia para: {user.username}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Erro ao criar perfil para {user.username}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\n✓ Processo concluído! {perfis_criados} perfis criados."))
        self.stdout.write(f"Total de perfis estendidos agora: {PerfilUsuarioEstendido.objects.count()}")

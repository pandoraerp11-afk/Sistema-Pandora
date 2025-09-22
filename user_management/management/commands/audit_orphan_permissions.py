from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = "Audita PermissaoPersonalizada com ações/módulos órfãos não mapeados no PermissionResolver."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=int, help="Filtrar por tenant_id")
        parser.add_argument("--user", type=int, help="Filtrar por user_id")

    def handle(self, *args, **options):
        from shared.services.permission_resolver import permission_resolver
        from user_management.models import PermissaoPersonalizada

        tenant_id = options.get("tenant")
        user_id = options.get("user")

        qs = PermissaoPersonalizada.objects.all()
        if tenant_id:
            qs = qs.filter(Q(scope_tenant_id=tenant_id) | Q(scope_tenant__isnull=True))
        if user_id:
            qs = qs.filter(user_id=user_id)

        action_map = permission_resolver._get_action_map()  # leitura
        known_actions = set(action_map.keys())

        orphans = []
        for p in qs.iterator():
            # Normaliza acao: pode ser verbo isolado (ex.: 'view') ou ação completa (VIEW_COTACAO)
            act = (p.acao or "").strip()
            modulo = (p.modulo or "").strip()
            full = None
            if act and modulo:
                # tentar compor
                full = f"{act.upper()}_{modulo.upper()}"
            elif act:
                full = act.upper()
            # Checar contra mapa
            if not full or full not in known_actions:
                orphans.append(p)

        if not orphans:
            self.stdout.write(self.style.SUCCESS("Nenhuma permissão órfã encontrada."))
            return

        self.stdout.write(self.style.WARNING(f"{len(orphans)} permissões órfãs encontradas:"))
        for p in orphans:
            self.stdout.write(
                f" - id={p.id} user_id={p.user_id} scope_tenant_id={p.scope_tenant_id} acao='{p.acao}' modulo='{p.modulo}' recurso='{p.recurso}' concedida={p.concedida}"
            )

        self.stdout.write("Sugestão: revisar action_map do PermissionResolver ou normalizar campos acao/modulo.")

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from core.models import CustomUser, Role, Tenant, TenantUser
from core.permissions import ModulePermissions


class Command(BaseCommand):
    """
    Comando para configurar permissões padrão do sistema e criar dados iniciais.
    """

    help = "Configura permissões padrão e cria dados iniciais do sistema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-superuser",
            action="store_true",
            help="Cria um superusuário padrão",
        )
        parser.add_argument(
            "--create-demo-tenant",
            action="store_true",
            help="Cria um tenant de demonstração",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando configuração do sistema..."))

        # Cria permissões personalizadas para cada módulo
        self.create_module_permissions()

        # Cria papéis padrão
        self.create_default_roles()

        if options["create_superuser"]:
            self.create_superuser()

        if options["create_demo_tenant"]:
            self.create_demo_tenant()

        self.stdout.write(self.style.SUCCESS("Configuração concluída com sucesso!"))

    def create_module_permissions(self):
        """
        Cria permissões personalizadas para cada módulo do sistema
        """
        self.stdout.write("Criando permissões personalizadas...")

        # Obtém o ContentType para o modelo Tenant (usado como referência)
        tenant_content_type = ContentType.objects.get_for_model(Tenant)

        for module_name, permissions in ModulePermissions.MODULE_PERMISSIONS.items():
            self.stdout.write(f"  Criando permissões para o módulo: {module_name}")

            for codename, name in permissions:
                permission, created = Permission.objects.get_or_create(
                    codename=codename, name=name, content_type=tenant_content_type
                )

                if created:
                    self.stdout.write(f"    ✓ Criada: {name}")
                else:
                    self.stdout.write(f"    - Já existe: {name}")

    def create_default_roles(self):
        """
        Cria papéis padrão do sistema
        """
        self.stdout.write("Criando papéis padrão...")

        # Papel de Administrador do Sistema
        admin_role, created = Role.objects.get_or_create(
            name="Administrador do Sistema",
            defaults={"description": "Acesso completo a todos os módulos e funcionalidades do sistema"},
        )

        if created:
            # Adiciona todas as permissões ao papel de administrador
            all_permissions = Permission.objects.all()
            admin_role.permissions.set(all_permissions)
            self.stdout.write("  ✓ Criado: Administrador do Sistema")
        else:
            self.stdout.write("  - Já existe: Administrador do Sistema")

        # Papel de Usuário Padrão
        user_role, created = Role.objects.get_or_create(
            name="Usuário Padrão", defaults={"description": "Acesso básico aos módulos principais do sistema"}
        )

        if created:
            # Adiciona permissões básicas de visualização
            basic_permissions = Permission.objects.filter(codename__startswith="view_")
            user_role.permissions.set(basic_permissions)
            self.stdout.write("  ✓ Criado: Usuário Padrão")
        else:
            self.stdout.write("  - Já existe: Usuário Padrão")

        # Papel de Gerente
        manager_role, created = Role.objects.get_or_create(
            name="Gerente", defaults={"description": "Acesso de gerenciamento aos módulos principais"}
        )

        if created:
            # Adiciona permissões de visualização, adição e edição
            manager_permissions = Permission.objects.filter(
                codename__in=[
                    "view_cliente",
                    "add_cliente",
                    "change_cliente",
                    "view_produto",
                    "add_produto",
                    "change_produto",
                    "view_servico",
                    "add_servico",
                    "change_servico",
                    "view_orcamento",
                    "add_orcamento",
                    "change_orcamento",
                    "approve_orcamento",
                ]
            )
            manager_role.permissions.set(manager_permissions)
            self.stdout.write("  ✓ Criado: Gerente")
        else:
            self.stdout.write("  - Já existe: Gerente")

    def create_superuser(self):
        """
        Cria um superusuário padrão
        """
        self.stdout.write("Criando superusuário...")

        if not CustomUser.objects.filter(username="admin").exists():
            CustomUser.objects.create_superuser(
                username="admin",
                email="admin@pandora.local",
                password="admin123",
                first_name="Administrador",
                last_name="Sistema",
            )
            self.stdout.write("  ✓ Superusuário criado: admin / admin123")
        else:
            self.stdout.write("  - Superusuário já existe")

    def create_demo_tenant(self):
        """
        Cria um tenant de demonstração
        """
        self.stdout.write("Criando tenant de demonstração...")

        demo_tenant, created = Tenant.objects.get_or_create(
            slug="demo",
            defaults={
                "name": "Empresa Demonstração",
                "company_name": "Empresa Demonstração Ltda",
                "trade_name": "Demo Corp",
                "cnpj": "12.345.678/0001-90",
                "email": "contato@demo.com",
                "phone": "(11) 99999-9999",
                "domain": "demo.pandora.local",
                "enabled_modules": {
                    "modules": [
                        "clientes",
                        "produtos",
                        "servicos",
                        "orcamentos",
                        "compras",
                        "financeiro",
                        "obras",
                        "estoque",
                        "agenda",
                        "apropriacao",
                        "aprovacoes",
                        "relatorios",
                    ]
                },
            },
        )

        if created:
            self.stdout.write("  ✓ Tenant de demonstração criado")

            # Cria um usuário administrador para o tenant
            demo_user, user_created = CustomUser.objects.get_or_create(
                username="demo_admin",
                defaults={
                    "email": "admin@demo.com",
                    "first_name": "Administrador",
                    "last_name": "Demo",
                    "is_active": True,
                },
            )

            if user_created:
                demo_user.set_password("demo123")
                demo_user.save()
                self.stdout.write("  ✓ Usuário demo criado: demo_admin / demo123")

            # Associa o usuário ao tenant como administrador
            tenant_user, tu_created = TenantUser.objects.get_or_create(
                tenant=demo_tenant, user=demo_user, defaults={"is_tenant_admin": True}
            )

            if tu_created:
                self.stdout.write("  ✓ Usuário associado ao tenant como administrador")
        else:
            self.stdout.write("  - Tenant de demonstração já existe")

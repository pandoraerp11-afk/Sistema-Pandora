from django.core.management.base import BaseCommand
from django.db import transaction

from clientes.models import Cliente
from core.models import CustomUser, Tenant, TenantUser
from portal_cliente.models import ContaCliente


class Command(BaseCommand):
    help = "Cria conta portal para testes do Portal Cliente"

    def get_cliente_nome(self, cliente):
        """Retorna o nome correto do cliente baseado no tipo (PF ou PJ)"""
        if cliente.tipo == "PF" and hasattr(cliente, "pessoafisica"):
            return cliente.pessoafisica.nome_completo
        elif cliente.tipo == "PJ" and hasattr(cliente, "pessoajuridica"):
            nome_fantasia = cliente.pessoajuridica.nome_fantasia
            razao_social = cliente.pessoajuridica.razao_social
            if nome_fantasia:
                return f"{nome_fantasia} ({razao_social})"
            else:
                return razao_social
        else:
            return f"Cliente #{cliente.id} ({cliente.get_tipo_display()})"

    def get_cliente_documento(self, cliente):
        """Retorna o documento principal do cliente"""
        if cliente.tipo == "PF" and hasattr(cliente, "pessoafisica"):
            return cliente.pessoafisica.cpf
        elif cliente.tipo == "PJ" and hasattr(cliente, "pessoajuridica"):
            return cliente.pessoajuridica.cnpj
        else:
            return "Não informado"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="cliente_teste", help="Username para o usuário de teste")
        parser.add_argument("--email", type=str, default="cliente@teste.com", help="Email para o usuário de teste")
        parser.add_argument("--password", type=str, default="123456", help="Senha para o usuário de teste")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        try:
            with transaction.atomic():
                # Buscar tenant da Bella Estética
                tenant = Tenant.objects.filter(name__icontains="bella").first()
                if not tenant:
                    # Tentar por razão social
                    tenant = Tenant.objects.filter(razao_social__icontains="bella").first()
                if not tenant:
                    tenant = Tenant.objects.first()
                    if not tenant:
                        self.stdout.write(self.style.ERROR("❌ Nenhum tenant encontrado! Execute o seed primeiro."))
                        return

                # Buscar ou criar usuário
                user, created = CustomUser.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": "Cliente",
                        "last_name": "Teste",
                        "is_active": True,
                    },
                )

                if created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Usuário criado: {username}"),
                        ending="\n",
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Usuário já existe: {username}"))

                # Buscar cliente da Bella Estética para associar
                # Primeiro tentar pessoa física
                cliente = (
                    Cliente.objects.filter(tenant=tenant, tipo="PF", pessoafisica__nome_completo__icontains="Maria")
                    .select_related("pessoafisica")
                    .first()
                )

                if not cliente:
                    # Tentar pessoa jurídica
                    cliente = (
                        Cliente.objects.filter(
                            tenant=tenant, tipo="PJ", pessoajuridica__nome_fantasia__icontains="Bella"
                        )
                        .select_related("pessoajuridica")
                        .first()
                    )

                if not cliente:
                    # Pegar qualquer cliente PF do tenant
                    cliente = Cliente.objects.filter(tenant=tenant, tipo="PF").select_related("pessoafisica").first()

                if not cliente:
                    # Pegar qualquer cliente PJ do tenant
                    cliente = Cliente.objects.filter(tenant=tenant, tipo="PJ").select_related("pessoajuridica").first()

                if not cliente:
                    # Pegar qualquer cliente do tenant
                    cliente = Cliente.objects.filter(tenant=tenant).first()

                if not cliente:
                    self.stdout.write(
                        self.style.ERROR("❌ Nenhum cliente encontrado! Execute o seed da Bella Estética primeiro.")
                    )
                    return

                # Garantir que o cliente tenha o portal habilitado (senão PermissionDenied)
                if not getattr(cliente, "portal_ativo", False):
                    cliente.portal_ativo = True
                    cliente.save(update_fields=["portal_ativo"])
                    self.stdout.write(self.style.SUCCESS("✅ Cliente atualizado: portal_ativo=True"))
                else:
                    self.stdout.write(self.style.SUCCESS("✅ Cliente já tinha portal_ativo=True"))

                # Garantir vínculo TenantUser para permitir login (acesso a empresa)
                tenant_user, tu_created = TenantUser.objects.get_or_create(
                    tenant=tenant, user=user, defaults={"is_tenant_admin": False}
                )
                if tu_created:
                    self.stdout.write(self.style.SUCCESS("✅ Vínculo TenantUser criado."))
                else:
                    self.stdout.write(self.style.WARNING("⚠️ Vínculo TenantUser já existia."))

                # Criar ou atualizar conta portal
                conta_cliente, created = ContaCliente.objects.get_or_create(
                    usuario=user,
                    cliente=cliente,
                    defaults={
                        "ativo": True,
                        "is_admin_portal": False,
                    },
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Conta Portal criada para: {self.get_cliente_nome(cliente)}")
                    )
                else:
                    conta_cliente.ativo = True
                    conta_cliente.save()
                    self.stdout.write(
                        self.style.WARNING(f"⚠️ Conta Portal já existe, ativada para: {self.get_cliente_nome(cliente)}")
                    )

                # Resumo final
                self.stdout.write(self.style.SUCCESS("\n🎉 PORTAL CLIENTE - CONFIGURAÇÃO DE TESTE PRONTA!"))
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(f"👤 Usuário: {user.username}")
                self.stdout.write(f"📧 Email: {user.email}")
                self.stdout.write(f"🔑 Senha: {password}")
                self.stdout.write(f"🏢 Tenant: {tenant.name}")
                self.stdout.write(f"👩‍💼 Cliente: {self.get_cliente_nome(cliente)}")
                self.stdout.write(f"📄 Documento: {self.get_cliente_documento(cliente)}")
                self.stdout.write(f"🏷️ Tipo: {cliente.get_tipo_display()}")
                self.stdout.write("🔗 URL: /portal_cliente/portal/")
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(self.style.SUCCESS("🚀 Agora você pode testar o Portal Cliente!"))

                # Mostrar estatísticas do cliente
                agendamentos_count = cliente.agendamentos.count()
                atendimentos_count = cliente.atendimentos.count()

                if agendamentos_count > 0 or atendimentos_count > 0:
                    self.stdout.write("\n📊 DADOS DO CLIENTE:")
                    self.stdout.write(f"📅 Agendamentos: {agendamentos_count}")
                    self.stdout.write(f"✅ Atendimentos: {atendimentos_count}")

                    # Contar fotos de evolução do cliente
                    fotos_count = cliente.fotos_evolucao.count()
                    if fotos_count > 0:
                        self.stdout.write(f"📸 Fotos de evolução: {fotos_count}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "\n⚠️ Cliente sem dados de teste. Execute: python manage.py seed_bella_estetica"
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro ao criar conta portal: {str(e)}"))
            raise

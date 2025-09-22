# funcionarios/management/commands/setup_funcionarios_estoque.py
# Comando para configurar integração funcionários-estoque

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Tenant
from estoque.models import Deposito
from funcionarios.models import Funcionario
from funcionarios.models_estoque import ConfiguracaoMaterial, PerfilFuncionario


class Command(BaseCommand):
    help = "Configura integração entre funcionários e estoque"

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, help="ID do tenant para configurar (opcional, padrão: todos)")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")

        tenants = Tenant.objects.filter(id=tenant_id) if tenant_id else Tenant.objects.all()

        for tenant in tenants:
            self.stdout.write(f"\n🔧 Configurando tenant: {tenant.nome}")
            self.setup_tenant(tenant)

    @transaction.atomic
    def setup_tenant(self, tenant):
        """Configura um tenant específico"""

        # 1. Criar perfis de estoque para funcionários existentes
        funcionarios_sem_perfil = Funcionario.objects.filter(tenant=tenant, perfil_estoque__isnull=True)

        created_profiles = 0
        for funcionario in funcionarios_sem_perfil:
            PerfilFuncionario.objects.get_or_create(
                funcionario=funcionario,
                defaults={
                    "pode_retirar_materiais": True,  # Padrão: pode retirar
                    "limite_valor_retirada": 500.00,  # Limite padrão
                    "necessita_aprovacao": True,  # Padrão: precisa aprovação
                },
            )
            created_profiles += 1

        self.stdout.write(f"   ✅ Criados {created_profiles} perfis de estoque")

        # 2. Configurar configurações globais
        config, created = ConfiguracaoMaterial.objects.get_or_create(
            tenant=tenant,
            defaults={
                "aprovacao_automatica_ate_valor": 100.00,
                "dias_prazo_devolucao": 30,
                "permite_retirada_sem_estoque": False,
                "notificar_supervisores": True,
                "campos_obrigatorios": ["motivo", "data_necessidade"],
            },
        )

        if created:
            self.stdout.write("   ✅ Configurações globais criadas")
        else:
            self.stdout.write("   ℹ️  Configurações globais já existem")

        # 3. Verificar depósitos disponíveis
        depositos_count = Deposito.objects.filter(tenant=tenant, ativo=True).count()
        self.stdout.write(f"   📦 Depósitos ativos disponíveis: {depositos_count}")

        # 4. Estatísticas finais
        funcionarios_total = Funcionario.objects.filter(tenant=tenant).count()
        perfis_total = PerfilFuncionario.objects.filter(funcionario__tenant=tenant).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"   ✨ Tenant configurado: {funcionarios_total} funcionários, {perfis_total} perfis de estoque"
            )
        )

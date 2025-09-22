from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Tenant
from fornecedores.models import Fornecedor, FornecedorPJ


class Command(BaseCommand):
    help = "Cria 4 fornecedores de teste (2 por cada um dos 2 primeiros tenants)."

    def add_arguments(self, parser):
        parser.add_argument("--per-tenant", type=int, default=2, help="Quantidade por tenant (default: 2)")
        parser.add_argument("--tenants", type=int, default=2, help="Quantidade de tenants (default: 2)")

    def handle(self, *args, **options):
        per_tenant = options["per_tenant"]
        tenants_count = options["tenants"]

        tenants = list(Tenant.objects.order_by("id")[:tenants_count])
        if not tenants:
            self.stdout.write(self.style.ERROR("Nenhum Tenant encontrado. Crie ao menos um Tenant."))
            return

        created_total = 0
        with transaction.atomic():
            for t_idx, tenant in enumerate(tenants, start=1):
                for i in range(1, per_tenant + 1):
                    fantasia = f"Fornecedor T{t_idx}-{i:02d}"
                    razao = f"Fornecedor Teste {t_idx}{i:02d} LTDA"
                    # Evita duplicidade por nome fantasia no mesmo tenant
                    exists = Fornecedor.objects.filter(tenant=tenant, pessoajuridica__nome_fantasia=fantasia).exists()
                    if exists:
                        self.stdout.write(self.style.WARNING(f"Já existe: {fantasia} (tenant {tenant.id})"))
                        continue

                    forn = Fornecedor.objects.create(
                        tenant=tenant,
                        tipo_pessoa="PJ",
                        tipo_fornecimento="AMBOS",
                        status="active",
                        status_homologacao="pendente",
                    )
                    FornecedorPJ.objects.create(
                        fornecedor=forn,
                        razao_social=razao,
                        nome_fantasia=fantasia,
                        cnpj=f"{t_idx:02d}.{i:03d}.{i:03d}/{t_idx:04d}-00",
                    )
                    created_total += 1

        self.stdout.write(self.style.SUCCESS(f"Criados {created_total} fornecedores de teste."))

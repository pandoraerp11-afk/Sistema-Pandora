from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from clientes.models import Cliente, PessoaJuridica
from core.models import Tenant
from obras.models import Obra


class Command(BaseCommand):
    help = "Cria 5 obras de teste para a empresa 'Delta Engenharia' no tenant atual ou padrão."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, help="ID do tenant para usar. Se omitido, usa o tenant padrão.")

    def _get_tenant(self, tenant_id=None):
        if tenant_id:
            try:
                return Tenant.objects.get(id=tenant_id, status="active")
            except Tenant.DoesNotExist:
                pass
        # tenta primeiro ativo existente
        tenant = Tenant.objects.filter(status="active").first()
        if tenant:
            return tenant
        # cria um tenant mínimo padrão
        sub = "default"
        if Tenant.objects.filter(subdomain=sub).exists():
            # acha um subdomínio livre
            base = "default"
            i = 1
            while Tenant.objects.filter(subdomain=f"{base}{i}").exists():
                i += 1
            sub = f"{base}{i}"
        tenant = Tenant.objects.create(name="Empresa Padrão", subdomain=sub, status="active")
        return tenant

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        tenant = self._get_tenant(tenant_id)
        self.stdout.write(self.style.NOTICE(f"Usando tenant: {tenant.name} (id={tenant.id})"))

        with transaction.atomic():
            # Cria ou recupera o cliente PJ "Delta Engenharia"
            cliente, created = Cliente.objects.get_or_create(
                tenant=tenant,
                tipo="PJ",
                email="contato@deltaengenharia.com",
                defaults={
                    "status": "active",
                    "telefone": "(11) 1111-1111",
                    "cidade": "São Paulo",
                    "estado": "SP",
                },
            )
            # Garante PessoaJuridica
            if created or not hasattr(cliente, "pessoajuridica"):
                PessoaJuridica.objects.update_or_create(
                    cliente=cliente,
                    defaults={
                        "razao_social": "Delta Engenharia Ltda",
                        "nome_fantasia": "Delta Engenharia",
                        "cnpj": "12.345.678/0001-99",
                    },
                )
            # Ajusta nome_display virtual via salvar os dados corretos
            # (nome_display é property; não precisa gravar)

            base_data_inicio = date.today() - timedelta(days=120)
            obras_infos = [
                ("Residencial Delta I", "construcao", "01234-000", "Rua Alfa, 100", "São Paulo", "SP", 1000000),
                ("Residencial Delta II", "construcao", "01234-001", "Rua Beta, 200", "São Paulo", "SP", 1200000),
                ("Delta Corporate Center", "andar", "04567-000", "Av. Paulista, 1500", "São Paulo", "SP", 8500000),
                ("Delta Mall", "loja", "05555-000", "Av. Shopping, 500", "São Paulo", "SP", 4500000),
                ("Condomínio Delta Park", "loteamento", "06666-000", "Estrada Parque, km 15", "Barueri", "SP", 2500000),
            ]

            created_count = 0
            for idx, (nome, tipo_obra, cep, endereco, cidade, estado, valor) in enumerate(obras_infos, start=1):
                data_prev = base_data_inicio + timedelta(days=240 + idx * 15)
                cno = f"DELTA-{timezone.now().strftime('%Y%m%d')}-{idx:02d}"
                obra, was_created = Obra.objects.get_or_create(
                    nome=nome,
                    defaults={
                        "tipo_obra": "construcao" if tipo_obra not in dict(Obra.TIPO_OBRA_CHOICES) else tipo_obra,
                        "cno": cno,
                        "cliente": cliente,
                        "endereco": endereco,
                        "cidade": cidade,
                        "estado": estado,
                        "cep": cep,
                        "data_inicio": base_data_inicio + timedelta(days=idx * 10),
                        "data_previsao_termino": data_prev,
                        "valor_contrato": valor,
                        "valor_total": valor * 1.1,
                        "status": "em_andamento",
                        "progresso": min(100, idx * 10),
                        "observacoes": "Gerado pelo seed de testes.",
                    },
                )
                created_count += 1 if was_created else 0

            self.stdout.write(self.style.SUCCESS(f"Seed concluído. Obras criadas: {created_count}/5"))

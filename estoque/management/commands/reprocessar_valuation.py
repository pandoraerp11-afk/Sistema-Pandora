from django.core.management.base import BaseCommand

from estoque.models import Deposito
from estoque.services import valuation as val_srv
from produtos.models import Produto


class Command(BaseCommand):
    help = "Reprocessa valuation (custo médio) de produtos PEPS através das camadas FIFO."

    def add_arguments(self, parser):
        parser.add_argument("--produto-id", type=int, help="ID específico do produto")
        parser.add_argument("--deposito-id", type=int, help="ID específico do depósito")

    def handle(self, *args, **options):
        produto_id = options.get("produto_id")
        deposito_id = options.get("deposito_id")
        produtos = Produto.objects.filter(id=produto_id) if produto_id else Produto.objects.all()
        depositos = Deposito.objects.filter(id=deposito_id) if deposito_id else Deposito.objects.all()
        count = 0
        for prod in produtos:
            if prod.tipo_custo != "peps":
                continue
            for dep in depositos:
                updated = val_srv.reprocessar_valuation(prod, dep)
                if updated is not None:
                    self.stdout.write(f"Produto {prod.id} Dep {dep.id} novo custo_medio={updated}")
                    count += 1
        self.stdout.write(self.style.SUCCESS(f"Reprocessamento concluído: {count} saldos atualizados."))

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from funcionarios.models import Ferias, Funcionario


class Command(BaseCommand):
    help = "Cria dados de exemplo para férias"

    def handle(self, *args, **options):
        self.stdout.write("Criando dados de exemplo para férias...")

        # Buscar todos os funcionários e tenants
        funcionarios = Funcionario.objects.select_related("tenant").all()

        if not funcionarios.exists():
            self.stdout.write(self.style.ERROR("Nenhum funcionário encontrado. Crie funcionários primeiro."))
            return

        # Status disponíveis
        status_choices = ["AGENDADA", "EM_ANDAMENTO", "CONCLUIDA", "CANCELADA"]

        ferias_criadas = 0

        for funcionario in funcionarios:
            # Criar 2-4 registros de férias para cada funcionário
            num_ferias = random.randint(2, 4)

            for i in range(num_ferias):
                # Período aquisitivo (ano anterior ao atual)
                ano_base = 2023 + i
                periodo_inicio = date(ano_base, 1, 1)
                periodo_fim = date(ano_base, 12, 31)

                # Data de início das férias (alguns meses após o período aquisitivo)
                inicio_ferias = date(ano_base + 1, random.randint(1, 12), random.randint(1, 28))

                # Dias de férias (entre 10 e 30 dias)
                dias_gozados = random.randint(10, 30)
                fim_ferias = inicio_ferias + timedelta(days=dias_gozados - 1)

                # Abono pecuniário (20% de chance)
                abono_pecuniario = random.choice([True, False, False, False, False])
                dias_abono = random.randint(1, 10) if abono_pecuniario else 0

                # Status aleatório
                status = random.choice(status_choices)

                # Valor pago (se concluída)
                valor_pago = None
                data_pagamento = None
                if status == "CONCLUIDA":
                    valor_pago = Decimal(str(random.uniform(1500.00, 5000.00)))
                    data_pagamento = inicio_ferias - timedelta(days=random.randint(1, 5))

                # Verificar se já existe férias para este período
                if not Ferias.objects.filter(
                    funcionario=funcionario, periodo_aquisitivo_inicio=periodo_inicio
                ).exists():
                    Ferias.objects.create(
                        tenant=funcionario.tenant,
                        funcionario=funcionario,
                        periodo_aquisitivo_inicio=periodo_inicio,
                        periodo_aquisitivo_fim=periodo_fim,
                        data_inicio=inicio_ferias,
                        data_fim=fim_ferias,
                        dias_gozados=dias_gozados,
                        abono_pecuniario=abono_pecuniario,
                        dias_abono=dias_abono,
                        status=status,
                        valor_pago=valor_pago,
                        data_pagamento=data_pagamento,
                    )
                    ferias_criadas += 1

                    self.stdout.write(
                        f"Férias criadas para {funcionario.nome_completo} - "
                        f"{inicio_ferias.strftime('%d/%m/%Y')} a {fim_ferias.strftime('%d/%m/%Y')} - "
                        f"Status: {status}"
                    )

        self.stdout.write(self.style.SUCCESS(f"Processo concluído! {ferias_criadas} registros de férias criados."))

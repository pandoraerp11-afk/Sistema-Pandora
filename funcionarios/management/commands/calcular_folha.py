# funcionarios/management/commands/calcular_folha.py

from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from funcionarios.models import Beneficio, Funcionario
from funcionarios.utils import CalculadoraFGTS, CalculadoraINSS, CalculadoraIRRF


class Command(BaseCommand):
    help = "Calcula e gera benefícios automáticos (INSS, FGTS, IRRF) para todos os funcionários ativos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mes", type=int, default=timezone.now().month, help="Mês de referência (padrão: mês atual)"
        )
        parser.add_argument(
            "--ano", type=int, default=timezone.now().year, help="Ano de referência (padrão: ano atual)"
        )
        parser.add_argument("--tenant-id", type=int, help="ID do tenant específico (opcional)")
        parser.add_argument("--dry-run", action="store_true", help="Executa sem salvar no banco (apenas simulação)")

    def handle(self, *args, **options):
        mes = options["mes"]
        ano = options["ano"]
        tenant_id = options.get("tenant_id")
        dry_run = options["dry_run"]

        data_referencia = date(ano, mes, 1)

        self.stdout.write(self.style.SUCCESS(f"Calculando folha para {mes:02d}/{ano}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO SIMULAÇÃO - Nenhum dado será salvo"))

        # Filtrar funcionários
        funcionarios = Funcionario.objects.filter(ativo=True)
        if tenant_id:
            funcionarios = funcionarios.filter(tenant_id=tenant_id)

        total_funcionarios = funcionarios.count()
        self.stdout.write(f"Processando {total_funcionarios} funcionários...")

        for funcionario in funcionarios:
            self.processar_funcionario(funcionario, data_referencia, dry_run)

        self.stdout.write(self.style.SUCCESS(f"Processamento concluído para {total_funcionarios} funcionários"))

    def processar_funcionario(self, funcionario, data_referencia, dry_run):
        """Processa cálculos para um funcionário específico"""

        salario_atual = funcionario.get_salario_atual()

        self.stdout.write(f"Processando: {funcionario.nome_completo} - R$ {salario_atual}")

        # Verifica se já existem benefícios para este mês
        beneficios_existentes = Beneficio.objects.filter(
            funcionario=funcionario, data_referencia=data_referencia, tipo_beneficio__in=["INSS", "FGTS", "IRRF"]
        )

        if beneficios_existentes.exists() and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"  Benefícios já existem para {funcionario.nome_completo} em {data_referencia.strftime('%m/%Y')}"
                )
            )
            return

        # Calcula INSS
        inss = CalculadoraINSS.calcular(salario_atual)
        self.stdout.write(f"  INSS: R$ {inss['valor_desconto']}")

        # Calcula FGTS
        fgts = CalculadoraFGTS.calcular(salario_atual)
        self.stdout.write(f"  FGTS: R$ {fgts['valor_fgts']}")

        # Calcula IRRF
        irrf = CalculadoraIRRF.calcular(salario_atual, funcionario.numero_dependentes)
        self.stdout.write(f"  IRRF: R$ {irrf['valor_irrf']}")

        if not dry_run:
            # Cria os benefícios
            if inss["valor_desconto"] > 0:
                Beneficio.objects.create(
                    tenant=funcionario.tenant,
                    funcionario=funcionario,
                    tipo_beneficio="INSS",
                    categoria="DESCONTO",
                    valor=inss["valor_desconto"],
                    data_referencia=data_referencia,
                    recorrente=True,
                    observacoes=f"Alíquota efetiva: {inss['aliquota_efetiva']}%",
                )

            if fgts["valor_fgts"] > 0:
                Beneficio.objects.create(
                    tenant=funcionario.tenant,
                    funcionario=funcionario,
                    tipo_beneficio="FGTS",
                    categoria="BENEFICIO",
                    valor=fgts["valor_fgts"],
                    data_referencia=data_referencia,
                    recorrente=True,
                    observacoes=f"Alíquota: {fgts['aliquota']}%",
                )

            if irrf["valor_irrf"] > 0:
                Beneficio.objects.create(
                    tenant=funcionario.tenant,
                    funcionario=funcionario,
                    tipo_beneficio="IRRF",
                    categoria="DESCONTO",
                    valor=irrf["valor_irrf"],
                    data_referencia=data_referencia,
                    recorrente=True,
                    observacoes=f"Alíquota: {irrf['aliquota']}% - Dependentes: {funcionario.numero_dependentes}",
                )

            self.stdout.write(self.style.SUCCESS(f"  Benefícios criados para {funcionario.nome_completo}"))

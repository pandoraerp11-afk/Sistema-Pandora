from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Executa passos finais de setup do módulo de estoque (migrations, permissões, seeds básicos)."
        " Não roda testes automaticamente para evitar custo em produção. Use --with-tests se desejar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-tests",
            action="store_true",
            help="Executa suíte de testes do app estoque ao final.",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Não executar migrate (caso já aplicado em pipeline anterior).",
        )
        parser.add_argument("--skip-permissions", action="store_true", help="Skip custom permissions creation.")
        parser.add_argument("--skip-seed", action="store_true", help="Skip basic seed data creation.")
        # Aliases legacy (PT-BR) — manter temporariamente
        parser.add_argument("--no-permissoes", action="store_true", help="[DEPRECATED] use --skip-permissions")
        parser.add_argument("--no-seed", action="store_true", help="[DEPRECATED] use --skip-seed")

    def handle(self, *args, **options):
        with_tests = options.get("with_tests")
        skip_migrate = options.get("skip_migrate")
        no_perms = options.get("skip_permissions") or options.get("no_permissoes")
        no_seed = options.get("skip_seed") or options.get("no_seed")

        self.stdout.write(self.style.SUCCESS("=== Setup Estoque Moderno ==="))
        if not skip_migrate:
            self.stdout.write("-> Aplicando migrations...")
            call_command("migrate", verbosity=1)

        if not no_perms:
            self.stdout.write("-> Criando permissões customizadas...")
            try:
                from estoque.permissions import criar_permissoes_estoque

                criar_permissoes_estoque()
            except Exception as e:  # pragma: no cover
                raise CommandError(f"Falha ao criar permissões: {e}") from e

        if not no_seed:
            self.stdout.write("-> Criando dados iniciais (tipos de movimento e depósito principal)...")
            self._seed_basico()

        if with_tests:
            self.stdout.write("-> Executando testes rápidos do app estoque...")
            call_command("test", "estoque.tests", verbosity=1)

        self.stdout.write(self.style.SUCCESS("Setup concluído com sucesso."))

    @transaction.atomic
    def _seed_basico(self):
        from estoque.models import Deposito, TipoMovimento

        tipos_movimento = [
            ("ENTRADA", "Entrada de Mercadoria"),
            ("SAIDA", "Saída de Mercadoria"),
            ("AJUSTE_POSITIVO", "Ajuste Positivo"),
            ("AJUSTE_NEGATIVO", "Ajuste Negativo"),
            ("TRANSFERENCIA", "Transferência entre Depósitos"),
            ("CONSUMO_BOM", "Consumo por BOM"),
            ("DEVOLUCAO", "Devolução"),
            ("PERDA", "Perda/Quebra"),
        ]
        for codigo, descricao in tipos_movimento:
            TipoMovimento.objects.get_or_create(codigo=codigo, defaults={"descricao": descricao})
        Deposito.objects.get_or_create(
            codigo="ALMOX01",
            defaults={"nome": "Almoxarifado Principal", "tipo": "ALMOX", "ativo": True},
        )

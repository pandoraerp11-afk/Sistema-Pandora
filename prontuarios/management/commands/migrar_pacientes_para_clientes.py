from django.core.management.base import BaseCommand

from clientes.models import Cliente, PessoaFisica
from core.models import Tenant
from prontuarios.models import Paciente, PerfilClinico


class Command(BaseCommand):
    help = "Migra registros de Paciente para Cliente/PessoaFisica e cria PerfilClinico quando possível. Não remove Paciente."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Apenas simula sem gravar alterações")
        parser.add_argument("--tenant", type=str, help="Subdomínio do tenant alvo (opcional)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        tenant_sub = options.get("tenant")

        tenants = Tenant.objects.all()
        if tenant_sub:
            tenants = tenants.filter(subdomain=tenant_sub)
        total_pac = 0
        migrados = 0
        perfis_criados = 0

        for tenant in tenants:
            pacientes = Paciente.objects.filter(tenant=tenant)
            total_pac += pacientes.count()
            for pac in pacientes:
                # Tenta localizar cliente PF existente por CPF
                cliente_pf = None
                if pac.cpf:
                    cliente_pf = Cliente.objects.filter(tenant=tenant, tipo="PF", pessoafisica__cpf=pac.cpf).first()
                if not cliente_pf:
                    # Criar cliente + PF
                    if dry_run:
                        self.stdout.write(
                            f"DRY-RUN Criaria Cliente PF para paciente {pac.nome_completo} ({pac.cpf}) no tenant {tenant.subdomain}"
                        )
                    else:
                        cliente_pf = Cliente.objects.create(
                            tenant=tenant,
                            tipo="PF",
                            nome_razao_social=pac.nome_completo if hasattr(Cliente, "nome_razao_social") else None,
                            status="active",
                            email=pac.email,
                            telefone=pac.telefone_principal,
                        )
                        # Criar PessoaFisica vinculada
                        PessoaFisica.objects.create(
                            cliente=cliente_pf,
                            nome_completo=pac.nome_completo,
                            cpf=pac.cpf,
                            rg=pac.rg,
                            data_nascimento=pac.data_nascimento,
                            sexo=pac.sexo if pac.sexo in ["M", "F", "O"] else None,
                            profissao=pac.profissao,
                        )
                        migrados += 1
                # Perfil Clínico
                if cliente_pf and not hasattr(cliente_pf, "perfil_clinico"):
                    if dry_run:
                        self.stdout.write(
                            f"DRY-RUN Criaria PerfilClinico para cliente {cliente_pf.id} derivado de paciente {pac.id}"
                        )
                    else:
                        PerfilClinico.objects.create(
                            tenant=tenant,
                            cliente=cliente_pf,
                            pessoa_fisica=getattr(cliente_pf, "pessoafisica", None),
                            tipo_sanguineo=pac.tipo_sanguineo,
                            alergias=pac.alergias,
                            medicamentos_uso=pac.medicamentos_uso,
                            doencas_cronicas=pac.doencas_cronicas,
                            cirurgias_anteriores=pac.cirurgias_anteriores,
                            tipo_pele=pac.tipo_pele,
                            fototipo=pac.fototipo,
                            historico_estetico=pac.historico_estetico,
                            contato_emergencia_nome=pac.contato_emergencia_nome,
                            contato_emergencia_telefone=pac.contato_emergencia_telefone,
                            contato_emergencia_parentesco=pac.contato_emergencia_parentesco,
                            termo_responsabilidade_assinado=pac.termo_responsabilidade_assinado,
                            data_assinatura_termo=pac.data_assinatura_termo,
                            lgpd_consentimento=pac.lgpd_consentimento,
                            data_consentimento_lgpd=pac.data_consentimento_lgpd,
                            observacoes_gerais=pac.observacoes_gerais,
                            ativo=True,
                        )
                        perfis_criados += 1
        self.stdout.write(self.style.SUCCESS(f"Total pacientes avaliados: {total_pac}"))
        self.stdout.write(self.style.SUCCESS(f"Clientes criados: {migrados}"))
        self.stdout.write(self.style.SUCCESS(f"Perfis clínicos criados: {perfis_criados}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Execução em modo DRY-RUN - nada foi gravado."))

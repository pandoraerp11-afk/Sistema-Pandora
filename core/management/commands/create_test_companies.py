"""
Comando para criar dados de teste com diferentes tipos de empresas
Inclui: empresas, usuários, clientes, fornecedores e produtos
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import CustomUser, Tenant, TenantUser


class Command(BaseCommand):
    """
    Comando para criar empresas de teste de diferentes segmentos.
    Cria empresas de construção civil e clínicas de estética.
    """

    help = "Cria empresas de teste para diferentes segmentos (construção civil e estética)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Remove empresas de teste existentes antes de criar novas",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Iniciando criação de dados de teste..."))

        if options["clear_existing"]:
            self.clear_test_data()

        # Cria empresas de construção civil
        self.create_construction_companies()

        # Cria clínicas de estética
        self.create_aesthetic_clinics()

        # Popula dados de teste para cada empresa criada
        self.populate_test_data()

        self.stdout.write(self.style.SUCCESS("✅ Dados de teste criados com sucesso!"))
        self.show_access_info()

    def clear_test_data(self):
        """Remove dados de teste existentes"""
        self.stdout.write("🧹 Removendo dados de teste existentes...")

        test_subdomains = [
            "construcao-silva",
            "engenharia-santos",
            "obras-oliveira",
            "clinica-bela-vida",
            "estetica-sublime",
            "spa-renovar",
        ]

        for subdomain in test_subdomains:
            try:
                tenant = Tenant.objects.get(subdomain=subdomain)
                # Remove usuários associados ao tenant
                TenantUser.objects.filter(tenant=tenant).delete()
                # Remove o tenant
                tenant.delete()
                self.stdout.write(f"  ❌ Removido: {subdomain}")
            except Tenant.DoesNotExist:
                pass

    def create_construction_companies(self):
        """Cria empresas de construção civil"""
        self.stdout.write("🏗️ Criando empresas de construção civil...")

        companies = [
            {
                "name": "Construtora Silva & Filhos",
                "subdomain": "construcao-silva",
                "company_name": "Silva & Filhos Construção Civil Ltda",
                "trade_name": "Construtora Silva",
                "cnpj": "12.345.678/0001-91",
                "email": "contato@construtorasilva.com.br",
                "phone": "(11) 3456-7890",
                "domain": "silva.pandora.local",
                "address": "Rua das Obras, 123",
                "city": "São Paulo",
                "state": "SP",
                "modules": [
                    "obras",
                    "compras",
                    "fornecedores",
                    "funcionarios",
                    "financeiro",
                    "estoque",
                    "produtos",
                    "agenda",
                    "apropriacao",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_silva",
                    "password": "silva123",
                    "first_name": "Carlos",
                    "last_name": "Silva",
                    "email": "carlos@construtorasilva.com.br",
                },
            },
            {
                "name": "Engenharia Santos",
                "subdomain": "engenharia-santos",
                "company_name": "Santos Engenharia e Construção S/A",
                "trade_name": "Engenharia Santos",
                "cnpj": "23.456.789/0001-92",
                "email": "info@engenhariasantos.com.br",
                "phone": "(11) 2345-6789",
                "domain": "santos.pandora.local",
                "address": "Av. dos Engenheiros, 456",
                "city": "Guarulhos",
                "state": "SP",
                "modules": [
                    "obras",
                    "orcamentos",
                    "compras",
                    "fornecedores",
                    "funcionarios",
                    "financeiro",
                    "estoque",
                    "produtos",
                    "quantificacao_obras",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_santos",
                    "password": "santos123",
                    "first_name": "Maria",
                    "last_name": "Santos",
                    "email": "maria@engenhariasantos.com.br",
                },
            },
            {
                "name": "Obras Oliveira",
                "subdomain": "obras-oliveira",
                "company_name": "Oliveira Obras e Reformas ME",
                "trade_name": "Obras Oliveira",
                "cnpj": "34.567.890/0001-93",
                "email": "contato@obrasoliveira.com.br",
                "phone": "(11) 3789-0123",
                "domain": "oliveira.pandora.local",
                "address": "Rua dos Pedreiros, 789",
                "city": "Osasco",
                "state": "SP",
                "modules": [
                    "obras",
                    "orcamentos",
                    "compras",
                    "funcionarios",
                    "mao_obra",
                    "financeiro",
                    "agenda",
                    "apropriacao",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_oliveira",
                    "password": "oliveira123",
                    "first_name": "João",
                    "last_name": "Oliveira",
                    "email": "joao@obrasoliveira.com.br",
                },
            },
        ]

        for company_data in companies:
            self.create_tenant(company_data, "Construção Civil")

    def create_aesthetic_clinics(self):
        """Cria clínicas de estética"""
        self.stdout.write("💄 Criando clínicas de estética...")

        clinics = [
            {
                "name": "Clínica Bela Vida",
                "subdomain": "clinica-bela-vida",
                "company_name": "Bela Vida Estética e Bem-Estar Ltda",
                "trade_name": "Clínica Bela Vida",
                "cnpj": "45.678.901/0001-94",
                "email": "contato@belavida.com.br",
                "phone": "(11) 4567-8901",
                "domain": "belavida.pandora.local",
                "address": "Rua da Beleza, 321",
                "city": "São Paulo",
                "state": "SP",
                "modules": [
                    "clientes",
                    "servicos",
                    "agenda",
                    "funcionarios",
                    "financeiro",
                    "produtos",
                    "estoque",
                    "prontuarios",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_belavida",
                    "password": "belavida123",
                    "first_name": "Ana",
                    "last_name": "Costa",
                    "email": "ana@belavida.com.br",
                },
            },
            {
                "name": "Estética Sublime",
                "subdomain": "estetica-sublime",
                "company_name": "Sublime Estética Avançada S/A",
                "trade_name": "Estética Sublime",
                "cnpj": "56.789.012/0001-95",
                "email": "atendimento@esteticasublime.com.br",
                "phone": "(11) 5678-9012",
                "domain": "sublime.pandora.local",
                "address": "Av. da Estética, 654",
                "city": "Campinas",
                "state": "SP",
                "modules": [
                    "clientes",
                    "servicos",
                    "orcamentos",
                    "agenda",
                    "funcionarios",
                    "financeiro",
                    "produtos",
                    "estoque",
                    "prontuarios",
                    "formularios",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_sublime",
                    "password": "sublime123",
                    "first_name": "Beatriz",
                    "last_name": "Ferreira",
                    "email": "beatriz@esteticasublime.com.br",
                },
            },
            {
                "name": "Spa Renovar",
                "subdomain": "spa-renovar",
                "company_name": "Renovar Spa e Estética ME",
                "trade_name": "Spa Renovar",
                "cnpj": "67.890.123/0001-96",
                "email": "info@sparenovar.com.br",
                "phone": "(11) 6789-0123",
                "domain": "renovar.pandora.local",
                "address": "Rua do Bem-Estar, 987",
                "city": "Santos",
                "state": "SP",
                "modules": [
                    "clientes",
                    "servicos",
                    "agenda",
                    "funcionarios",
                    "financeiro",
                    "produtos",
                    "estoque",
                    "prontuarios",
                    "aprovacoes",
                    "relatorios",
                ],
                "admin_user": {
                    "username": "admin_renovar",
                    "password": "renovar123",
                    "first_name": "Carla",
                    "last_name": "Mendes",
                    "email": "carla@sparenovar.com.br",
                },
            },
        ]

        for clinic_data in clinics:
            self.create_tenant(clinic_data, "Clínica de Estética")

    def create_tenant(self, tenant_data, segment):
        """Cria um tenant com os dados fornecidos"""
        try:
            tenant, created = Tenant.objects.get_or_create(
                subdomain=tenant_data["subdomain"],
                defaults={
                    "name": tenant_data["name"],
                    "razao_social": tenant_data["company_name"],
                    "cnpj": tenant_data["cnpj"],
                    "email": tenant_data["email"],
                    "telefone": tenant_data["phone"],
                    "tipo_pessoa": "PJ",
                    "status": "active",
                    "enabled_modules": {"modules": tenant_data["modules"]},
                },
            )

            if created:
                self.stdout.write(f"  ✅ Criado: {tenant_data['name']} ({tenant_data['subdomain']})")

                # Cria endereço principal
                from core.models import Endereco

                endereco, endereco_created = Endereco.objects.get_or_create(
                    tenant=tenant,
                    tipo="PRINCIPAL",
                    defaults={
                        "logradouro": tenant_data.get("address", "Endereço não informado"),
                        "numero": "123",
                        "bairro": "Centro",
                        "cidade": tenant_data.get("city", "São Paulo"),
                        "uf": tenant_data.get("state", "SP"),
                        "cep": "01234-567",
                        "pais": "Brasil",
                    },
                )

                if endereco_created:
                    self.stdout.write(f"    📍 Endereço criado para {tenant_data['name']}")

                # Cria usuário administrador
                admin_data = tenant_data["admin_user"]
                user, user_created = CustomUser.objects.get_or_create(
                    username=admin_data["username"],
                    defaults={
                        "email": admin_data["email"],
                        "first_name": admin_data["first_name"],
                        "last_name": admin_data["last_name"],
                        "is_active": True,
                        "is_staff": False,
                        "is_superuser": False,
                    },
                )

                if user_created:
                    user.set_password(admin_data["password"])
                    user.save()
                    self.stdout.write(f"    👤 Usuário criado: {admin_data['username']}")

                # Associa usuário ao tenant
                tenant_user, tu_created = TenantUser.objects.get_or_create(
                    tenant=tenant, user=user, defaults={"is_tenant_admin": True}
                )

                if tu_created:
                    self.stdout.write("    🔗 Usuário associado como admin do tenant")

            else:
                self.stdout.write(f"  ⚠️  Já existe: {tenant_data['name']} ({tenant_data['subdomain']})")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Erro ao criar {tenant_data['name']}: {str(e)}"))

    def populate_test_data(self):
        """Popula dados de teste para todas as empresas criadas"""
        self.stdout.write("📦 Populando dados de teste...")

        construction_subdomains = ["construcao-silva", "engenharia-santos", "obras-oliveira"]
        aesthetic_subdomains = ["clinica-bela-vida", "estetica-sublime", "spa-renovar"]

        # Popula dados para empresas de construção
        for subdomain in construction_subdomains:
            try:
                tenant = Tenant.objects.get(subdomain=subdomain)
                self.create_construction_data(tenant)
            except Tenant.DoesNotExist:
                pass

        # Popula dados para clínicas de estética
        for subdomain in aesthetic_subdomains:
            try:
                tenant = Tenant.objects.get(subdomain=subdomain)
                self.create_aesthetic_data(tenant)
            except Tenant.DoesNotExist:
                pass

    def create_construction_data(self, tenant):
        """Cria dados de teste específicos para empresas de construção"""
        self.stdout.write(f"  🏗️ Populando {tenant.name}...")

        # Clientes para construção
        construction_clients = [
            {
                "nome": "João Silva Residencial",
                "email": "joao.silva@email.com",
                "telefone": "(11) 99999-1111",
                "tipo_pessoa": "PF",
                "cpf": "123.456.789-01",
            },
            {
                "nome": "Incorporadora Sunset",
                "razao_social": "Sunset Incorporações Ltda",
                "email": "contato@incorporadorasunset.com.br",
                "telefone": "(11) 3333-4444",
                "tipo_pessoa": "PJ",
                "cnpj": "12.345.678/0001-99",
            },
            {
                "nome": "Construtora Alpha",
                "razao_social": "Alpha Construções S/A",
                "email": "obras@alpha.com.br",
                "telefone": "(11) 2222-3333",
                "tipo_pessoa": "PJ",
                "cnpj": "98.765.432/0001-88",
            },
        ]

        # Fornecedores para construção
        construction_suppliers = [
            {
                "nome": "Cimentos São Paulo",
                "razao_social": "São Paulo Cimentos e Materiais Ltda",
                "email": "vendas@cimentossp.com.br",
                "telefone": "(11) 4444-5555",
                "cnpj": "11.222.333/0001-44",
            },
            {
                "nome": "Ferro e Aço Brasil",
                "razao_social": "Brasil Ferro e Aço Indústria S/A",
                "email": "comercial@ferroaco.com.br",
                "telefone": "(11) 5555-6666",
                "cnpj": "22.333.444/0001-55",
            },
            {
                "nome": "Madeiras Premium",
                "razao_social": "Premium Madeiras e Acabamentos ME",
                "email": "vendas@madeiraspremium.com.br",
                "telefone": "(11) 6666-7777",
                "cnpj": "33.444.555/0001-66",
            },
        ]

        # Produtos para construção
        construction_products = [
            {
                "nome": "Cimento Portland CP II-Z-32",
                "codigo": "CIM001",
                "categoria": "Cimentos",
                "preco_venda": 25.90,
                "unidade": "SC",
            },
            {
                "nome": "Tijolo Cerâmico 6 Furos",
                "codigo": "TIJ001",
                "categoria": "Alvenaria",
                "preco_venda": 0.45,
                "unidade": "UN",
            },
            {
                "nome": "Vergalhão CA-50 12mm",
                "codigo": "VER001",
                "categoria": "Ferro e Aço",
                "preco_venda": 8.50,
                "unidade": "KG",
            },
            {
                "nome": "Areia Média Lavada",
                "codigo": "ARE001",
                "categoria": "Agregados",
                "preco_venda": 35.00,
                "unidade": "M3",
            },
            {
                "nome": "Brita 1 Granito",
                "codigo": "BRI001",
                "categoria": "Agregados",
                "preco_venda": 42.00,
                "unidade": "M3",
            },
        ]

        self.create_clients(tenant, construction_clients)
        self.create_suppliers(tenant, construction_suppliers)
        self.create_products(tenant, construction_products)

    def create_aesthetic_data(self, tenant):
        """Cria dados de teste específicos para clínicas de estética"""
        self.stdout.write(f"  💄 Populando {tenant.name}...")

        # Clientes para estética
        aesthetic_clients = [
            {
                "nome": "Maria Oliveira",
                "email": "maria.oliveira@email.com",
                "telefone": "(11) 91111-2222",
                "tipo_pessoa": "PF",
                "cpf": "987.654.321-09",
            },
            {
                "nome": "Ana Costa Silva",
                "email": "ana.costa@gmail.com",
                "telefone": "(11) 92222-3333",
                "tipo_pessoa": "PF",
                "cpf": "456.789.123-45",
            },
            {
                "nome": "Fernanda Santos",
                "email": "fernanda.santos@hotmail.com",
                "telefone": "(11) 93333-4444",
                "tipo_pessoa": "PF",
                "cpf": "789.123.456-78",
            },
            {
                "nome": "Juliana Ferreira",
                "email": "ju.ferreira@yahoo.com",
                "telefone": "(11) 94444-5555",
                "tipo_pessoa": "PF",
                "cpf": "321.654.987-32",
            },
        ]

        # Fornecedores para estética
        aesthetic_suppliers = [
            {
                "nome": "Cosméticos Belle",
                "razao_social": "Belle Cosméticos e Produtos de Beleza Ltda",
                "email": "vendas@cosmeticosbelle.com.br",
                "telefone": "(11) 7777-8888",
                "cnpj": "44.555.666/0001-77",
            },
            {
                "nome": "Equipamentos Laser Pro",
                "razao_social": "Laser Pro Equipamentos Estéticos S/A",
                "email": "comercial@laserpro.com.br",
                "telefone": "(11) 8888-9999",
                "cnpj": "55.666.777/0001-88",
            },
            {
                "nome": "Dermocosméticos Premium",
                "razao_social": "Premium Dermocosméticos Importação ME",
                "email": "vendas@dermopremium.com.br",
                "telefone": "(11) 9999-0000",
                "cnpj": "66.777.888/0001-99",
            },
        ]

        # Produtos/Serviços para estética
        aesthetic_products = [
            {
                "nome": "Limpeza de Pele Profunda",
                "codigo": "SERV001",
                "categoria": "Tratamentos Faciais",
                "preco_venda": 120.00,
                "unidade": "UN",
            },
            {
                "nome": "Massagem Relaxante",
                "codigo": "SERV002",
                "categoria": "Massagens",
                "preco_venda": 180.00,
                "unidade": "UN",
            },
            {
                "nome": "Depilação a Laser - Pernas",
                "codigo": "SERV003",
                "categoria": "Depilação",
                "preco_venda": 250.00,
                "unidade": "UN",
            },
            {
                "nome": "Peeling Químico",
                "codigo": "SERV004",
                "categoria": "Tratamentos Faciais",
                "preco_venda": 200.00,
                "unidade": "UN",
            },
            {
                "nome": "Sérum Anti-Idade Premium",
                "codigo": "PROD001",
                "categoria": "Produtos",
                "preco_venda": 89.90,
                "unidade": "UN",
            },
            {
                "nome": "Creme Hidratante Facial",
                "codigo": "PROD002",
                "categoria": "Produtos",
                "preco_venda": 45.00,
                "unidade": "UN",
            },
        ]

        self.create_clients(tenant, aesthetic_clients)
        self.create_suppliers(tenant, aesthetic_suppliers)
        self.create_products(tenant, aesthetic_products)

    def create_clients(self, tenant, clients_data):
        """Cria clientes para o tenant"""
        try:
            from clientes.models import Cliente, PessoaFisica, PessoaJuridica

            for client_data in clients_data:
                try:
                    # Cria o cliente base
                    cliente, created = Cliente.objects.get_or_create(
                        tenant=tenant,
                        email=client_data["email"],
                        defaults={
                            "telefone": client_data["telefone"],
                            "tipo": client_data["tipo_pessoa"],
                            "status": "active",
                        },
                    )

                    if created:
                        # Cria dados específicos baseado no tipo
                        if client_data["tipo_pessoa"] == "PF":
                            pessoa_fisica, pf_created = PessoaFisica.objects.get_or_create(
                                cliente=cliente,
                                defaults={
                                    "nome_completo": client_data["nome"],
                                    "cpf": client_data.get("cpf", "000.000.000-00"),
                                    "data_nascimento": timezone.now().date(),
                                },
                            )
                        else:  # PJ
                            pessoa_juridica, pj_created = PessoaJuridica.objects.get_or_create(
                                cliente=cliente,
                                defaults={
                                    "razao_social": client_data.get("razao_social", client_data["nome"]),
                                    "nome_fantasia": client_data["nome"],
                                    "cnpj": client_data.get("cnpj", "00.000.000/0000-00"),
                                },
                            )

                        self.stdout.write(f"    👤 Cliente criado: {client_data['nome']}")

                except Exception as e:
                    self.stdout.write(f"    ⚠️ Erro ao criar cliente {client_data['nome']}: {str(e)}")

        except ImportError:
            self.stdout.write(f"    ⚠️ Módulo de clientes não disponível para {tenant.name}")

    def create_suppliers(self, tenant, suppliers_data):
        """Cria fornecedores para o tenant"""
        try:
            from fornecedores.models import CategoriaFornecedor, Fornecedor, FornecedorPJ

            for supplier_data in suppliers_data:
                try:
                    # Verificar se já existe pelo email
                    if (
                        not Fornecedor.objects.filter(tenant=tenant)
                        .filter(pessoajuridica__nome_fantasia=supplier_data["nome"])
                        .exists()
                    ):
                        # Criar categoria se não existir
                        categoria, created = CategoriaFornecedor.objects.get_or_create(
                            tenant=tenant,
                            nome="Fornecedor Padrão",
                            defaults={"descricao": "Categoria padrão para fornecedores"},
                        )

                        # Criar fornecedor
                        fornecedor = Fornecedor.objects.create(
                            tenant=tenant,
                            tipo_pessoa="PJ",
                            tipo_fornecimento="PRODUTOS",
                            categoria=categoria,
                            status="active",
                            status_homologacao="aprovado",
                        )

                        # Criar dados de PJ
                        FornecedorPJ.objects.create(
                            fornecedor=fornecedor,
                            razao_social=supplier_data["razao_social"],
                            nome_fantasia=supplier_data["nome"],
                            cnpj=supplier_data["cnpj"],
                        )

                        self.stdout.write(f"    🏭 Fornecedor criado: {supplier_data['nome']}")
                    else:
                        self.stdout.write(f"    🏭 Fornecedor já existe: {supplier_data['nome']}")
                except Exception as e:
                    self.stdout.write(f"    ⚠️ Erro ao criar fornecedor {supplier_data['nome']}: {str(e)}")

        except ImportError:
            self.stdout.write(f"    ⚠️ Módulo de fornecedores não disponível para {tenant.name}")

    def create_products(self, tenant, products_data):
        """Cria produtos/serviços para o tenant - produtos são globais, não por tenant"""
        try:
            from cadastros_gerais.models import UnidadeMedida
            from produtos.models import Categoria, Produto

            # Verificar se existem unidades de medida
            unidade_un, created = UnidadeMedida.objects.get_or_create(
                simbolo="UN", defaults={"nome": "Unidade", "descricao": "Unidade básica"}
            )

            for product_data in products_data:
                try:
                    # Verificar se produto já existe pelo nome
                    if not Produto.objects.filter(nome=product_data["nome"]).exists():
                        # Criar categoria se não existir
                        categoria, created = Categoria.objects.get_or_create(
                            nome=product_data["categoria"],
                            defaults={"descricao": f"Categoria {product_data['categoria']}"},
                        )

                        # Criar produto (sem campo tenant)
                        Produto.objects.create(
                            nome=product_data["nome"],
                            categoria=categoria,
                            unidade=unidade_un,
                            preco_unitario=product_data["preco_venda"],
                            preco_custo=product_data["preco_venda"] * 0.7,  # 70% do preço de venda como custo
                            estoque_atual=10,
                            estoque_minimo=5,
                            controla_estoque=True,
                            ativo=True,
                        )
                        self.stdout.write(f"    📦 Produto criado: {product_data['nome']}")
                    else:
                        self.stdout.write(f"    📦 Produto já existe: {product_data['nome']}")
                except Exception as e:
                    self.stdout.write(f"    ⚠️ Erro ao criar produto {product_data['nome']}: {str(e)}")

        except ImportError:
            self.stdout.write(f"    ⚠️ Módulo de produtos não disponível para {tenant.name}")

    def show_access_info(self):
        """Mostra informações de acesso às empresas criadas"""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("📋 INFORMAÇÕES DE ACESSO:"))
        self.stdout.write("")

        self.stdout.write(self.style.WARNING("🏗️  EMPRESAS DE CONSTRUÇÃO CIVIL:"))
        construction_access = [
            ("Construtora Silva & Filhos", "silva.pandora.local", "admin_silva", "silva123"),
            ("Engenharia Santos", "santos.pandora.local", "admin_santos", "santos123"),
            ("Obras Oliveira", "oliveira.pandora.local", "admin_oliveira", "oliveira123"),
        ]

        for name, domain, username, password in construction_access:
            self.stdout.write(f"  🏢 {name}")
            self.stdout.write(f"     🌐 Domínio: {domain}")
            self.stdout.write(f"     👤 Usuário: {username}")
            self.stdout.write(f"     🔑 Senha: {password}")
            self.stdout.write("")

        self.stdout.write(self.style.WARNING("💄 CLÍNICAS DE ESTÉTICA:"))
        aesthetic_access = [
            ("Clínica Bela Vida", "belavida.pandora.local", "admin_belavida", "belavida123"),
            ("Estética Sublime", "sublime.pandora.local", "admin_sublime", "sublime123"),
            ("Spa Renovar", "renovar.pandora.local", "admin_renovar", "renovar123"),
        ]

        for name, domain, username, password in aesthetic_access:
            self.stdout.write(f"  💅 {name}")
            self.stdout.write(f"     🌐 Domínio: {domain}")
            self.stdout.write(f"     👤 Usuário: {username}")
            self.stdout.write(f"     🔑 Senha: {password}")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("💡 Para acessar, use o comando:"))
        self.stdout.write("   python manage.py runserver")
        self.stdout.write("")

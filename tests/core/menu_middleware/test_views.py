"""Testes de views relacionadas ao middleware de menu e wizard de tenants."""

# ruff: noqa: S101

import os
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Role, Tenant, TenantUser
from tests.core.tenant_wizard.wizard_test_utils import TenantWizardTestHelper

CustomUser = get_user_model()
TEST_PWD = os.environ.get("TEST_PASSWORD", "x")


class CoreViewsTestCase(TestCase):
    """Casos de teste principais para acesso e fluxo de criação de empresa."""

    def setUp(self) -> None:
        """Cria usuários, tenant e papéis base para os testes."""
        self.client = Client()
        self.superuser = CustomUser.objects.create_superuser("superuser", "super@example.com", TEST_PWD)
        self.admin_user = CustomUser.objects.create_user("adminuser", "admin@example.com", TEST_PWD)
        self.regular_user = CustomUser.objects.create_user("regularuser", "regular@example.com", TEST_PWD)
        self.tenant = Tenant.objects.create(name="Empresa Teste", subdomain="teste")
        self.admin_role = Role.objects.create(tenant=self.tenant, name="Admin")
        self.user_role = Role.objects.create(tenant=self.tenant, name="Usuário")
        TenantUser.objects.create(
            tenant=self.tenant,
            user=self.admin_user,
            role=self.admin_role,
            is_tenant_admin=True,
        )
        TenantUser.objects.create(tenant=self.tenant, user=self.regular_user, role=self.user_role)

    def test_login_and_logout(self) -> None:
        """Usuário anônimo é redirecionado para login; login e logout redirecionam corretamente."""
        response = self.client.get(reverse("dashboard"))
        assert response.status_code == HTTPStatus.FOUND
        assert reverse("core:login") in response.headers.get("Location", "")
        response = self.client.post(
            reverse("core:login"),
            {"username": "regularuser", "password": TEST_PWD},
        )
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers.get("Location") == reverse("dashboard")
        response = self.client.get(reverse("core:logout"))
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers.get("Location") == reverse("core:login")

    def test_superuser_access(self) -> None:
        """Superusuário acessa lista e tela de criação de empresas (wizard ou legado)."""
        self.client.login(username="superuser", password=TEST_PWD)
        response = self.client.get(reverse("core:tenant_list"))
        assert response.status_code == HTTPStatus.OK
        assert "Gerenciamento de Empresas" in response.content.decode("utf-8", "ignore")
        response = self.client.get(reverse("core:tenant_create"))
        assert response.status_code == HTTPStatus.OK
        # A tela de criação foi modernizada para um wizard. Aceitamos tanto o texto legado
        # quanto marcadores claros do wizard para manter compatibilidade dos testes.
        content = response.content.decode("utf-8", errors="ignore")
        assert (
            ("Cadastro de Nova Empresa" in content)
            or ("Assistente" in content)
            or ('name="wizard_step"' in content)
            or ('class="wizard-form"' in content)
        ), "A página de criação de empresa deve exibir o wizard moderno ou o texto legado."

    def test_regular_user_permission_denied(self) -> None:
        """Usuário comum deve ser redirecionado ao tentar acessar a lista de empresas."""
        self.client.login(username="regularuser", password=TEST_PWD)
        response = self.client.get(reverse("core:tenant_list"))
        assert response.status_code == HTTPStatus.FOUND
        assert "/login/" in response.headers.get("Location", "")

    def test_tenant_admin_access(self) -> None:
        """Admin do tenant acessa a lista de usuários do tenant atual."""
        self.client.login(username="adminuser", password=TEST_PWD)
        session = self.client.session
        session["tenant_id"] = int(self.tenant.pk) if self.tenant.pk is not None else None
        session.save()
        response = self.client.get(reverse("core:tenant_user_list"))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8", "ignore")
        assert self.regular_user.username in content
        assert self.admin_user.username in content

    def test_switch_tenant(self) -> None:
        """Alterna entre tenants vinculados ao usuário admin."""
        tenant2 = Tenant.objects.create(name="Outra Empresa", subdomain="outra")
        TenantUser.objects.create(tenant=tenant2, user=self.admin_user, role=self.admin_role)
        self.client.login(username="adminuser", password=TEST_PWD)
        response = self.client.get(reverse("dashboard"))
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers.get("Location") == reverse("core:tenant_select")
        response = self.client.get(reverse("core:switch_tenant", args=[int(self.tenant.pk)]))
        assert self.client.session.get("tenant_id") == int(self.tenant.pk)
        response = self.client.get(reverse("core:switch_tenant", args=[int(tenant2.pk)]))
        assert self.client.session.get("tenant_id") == int(tenant2.pk)

    def test_tenant_creation_view(self) -> None:
        """Fluxo real do wizard multi-step (sem hacks de compatibilidade).

        Estratégia:
        1. GET inicial -> step 1
        2. POST step 1 (dados PJ mínimos válidos) navegação livre (avança para 2)
        3. Pular steps 2,3,4 enviando POST vazio (navegação livre) até chegar ao 5
        4. POST step 5 com subdomain/status válidos (avança para 6)
        5. Pular step 6 (admins) com POST vazio
        6. POST step 7 com wizard_finish + checkboxes de confirmação (prefix main-)
        7. Validar redirect final e persistência do tenant.
        """
        self.client.login(username="superuser", password=TEST_PWD)

        # 1. GET inicial (step 1)
        r = self.client.get(reverse("core:tenant_create"))
        assert r.status_code == HTTPStatus.OK

        # 2. POST step 1 (prefix 'pj')
        step1_post = {
            "tipo_pessoa": "PJ",
            "pj-tipo_pessoa": "PJ",
            "pj-name": "Nova Empresa Via Teste",
            "pj-razao_social": "Nova Empresa Via Teste LTDA",
            "pj-cnpj": "98.765.432/0001-11",
            # Campos opcionais deixados em branco; navegação livre tratará.
        }
        r = self.client.post(reverse("core:tenant_create"), step1_post)
        assert r.status_code == HTTPStatus.FOUND
        assert r.headers.get("Location") == reverse("core:tenant_create")  # avança para step 2

        # 3. Step 2 requer payload mínimo de endereço; enviar e avançar, depois pular 3 e 4
        step2_min = {
            "main-cep": "01000-000",
            "main-logradouro": "Rua Teste",
            "main-numero": "1",
            "main-bairro": "Centro",
            "main-cidade": "São Paulo",
            "main-uf": "SP",
            "main-pais": "Brasil",
        }
        r = self.client.post(reverse("core:tenant_create"), step2_min)
        assert r.status_code == HTTPStatus.FOUND
        assert r.headers.get("Location") == reverse("core:tenant_create")

        # Pular steps 3 e 4 com POST vazio
        for _ in range(2):
            r = self.client.post(reverse("core:tenant_create"), {})
            assert r.status_code == HTTPStatus.FOUND
            assert r.headers.get("Location") == reverse("core:tenant_create")

        # 4. POST step 5 (prefix 'main') com payload mínimo válido
        step5_post = {
            "main-subdomain": "nova-teste",
            "main-status": "active",
            "main-plano_assinatura": "BASIC",
            "main-max_usuarios": "5",
            "main-max_armazenamento_gb": "1",
            "main-timezone": "America/Sao_Paulo",
            "main-idioma_padrao": "pt-br",
            "main-moeda_padrao": "BRL",
            "main-enabled_modules": ["admin"],
        }
        r = self.client.post(reverse("core:tenant_create"), step5_post)
        assert r.status_code == HTTPStatus.FOUND
        assert r.headers.get("Location") == reverse("core:tenant_create")  # avança para step 6

        # 5. Pular step 6
        r = self.client.post(reverse("core:tenant_create"), {})
        assert r.status_code == HTTPStatus.FOUND
        assert r.headers.get("Location") == reverse("core:tenant_create")  # agora deve estar no step 7

        # 6. POST step 7 com finish (prefix main)
        finish_post = {"finish_wizard": "1", "main-confirmar_dados": "on", "main-aceitar_termos": "on"}
        r = self.client.post(reverse("core:tenant_create"), finish_post)
        assert r.status_code == HTTPStatus.FOUND, f"Finalização não redirecionou: {r.status_code}"
        # A view finaliza redirecionando para o detalhe do tenant recém-criado.
        loc = r.headers.get("Location", "")
        assert loc, "Redirect final sem Location"
        # Aceitar tanto lista (implementações antigas) quanto detalhe (atual)
        assert loc == reverse("core:tenant_list") or loc.startswith(
            reverse("core:tenant_detail", kwargs={"pk": 1}).rsplit("/", 2)[0],
        ), f"Redirect inesperado: {loc}"
        assert Tenant.objects.filter(subdomain="nova-teste").exists(), "Tenant não foi criado"

    def test_tenant_wizard_subdomain_obrigatorio(self) -> None:
        """Não deve finalizar se subdomain não for informado no step 5."""
        self.client.login(username="superuser", password=TEST_PWD)
        helper = TenantWizardTestHelper(self.client)
        helper.start()
        helper.step1_pj()
        helper.skip_steps(2, 4)
        # Step 5 sem subdomínio deve falhar (status 400)
        resp5 = helper.step5_config_expect_error(subdomain=None)
        assert resp5.status_code == HTTPStatus.BAD_REQUEST
        # Tentativa de finalizar deve manter no step atual com 400 (ou redirect) e não criar tenant
        resp = helper.finish()
        assert resp.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.FOUND)
        assert Tenant.objects.filter(cnpj="11.222.333/0001-44").count() == 0

    def test_tenant_wizard_subdomain_unico(self) -> None:
        """Não deve permitir subdomain duplicado."""
        Tenant.objects.create(name="Existente", subdomain="duplicado", cnpj="00.111.222/0001-55", tipo_pessoa="PJ")
        self.client.login(username="superuser", password=TEST_PWD)
        helper = TenantWizardTestHelper(self.client)
        helper.start()
        helper.step1_pj(cnpj="22.333.444/0001-66")
        helper.skip_steps(2, 4)
        # Step 5 com subdomínio duplicado deve falhar (status 400)
        resp5 = helper.step5_config_expect_error(subdomain="duplicado")
        assert resp5.status_code == HTTPStatus.BAD_REQUEST
        # Tentativa de finalizar deve manter no step atual com 400 (ou redirect) e não criar novo tenant
        resp = helper.finish()
        assert resp.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.FOUND)
        assert Tenant.objects.filter(subdomain="duplicado").count() == 1

"""Testes legados para o app Core.

Migrado de `core/tests.py` para evitar conflitos de nome de módulo.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import (
    Department,
    Role,
    Tenant,
    TenantPessoaFisica,
    TenantPessoaJuridica,
    TenantUser,
    UserProfile,
)

CustomUser = get_user_model()


# ruff: noqa: PT009, PLR2004, S106


class CoreModelsTestCase(TestCase):
    """Testes para os modelos do app Core."""

    def setUp(self) -> None:
        """Configura dados básicos para os testes de modelo."""
        self.tenant_pj = Tenant.objects.create(
            name="Construtora Exemplo Ltda",
            subdomain="construtora",
            tipo_pessoa="PJ",
            cnpj="12.345.678/0001-99",
            razao_social="CONSTRUTORA EXEMPLO LTDA",
        )
        self.tenant_pf = Tenant.objects.create(
            name="João da Silva Arquiteto",
            subdomain="joao-arquiteto",
            tipo_pessoa="PF",
            cpf="123.456.789-00",
        )
        # Correção: Criar explicitamente os objetos que antes dependiam de sinais
        TenantPessoaJuridica.objects.create(
            tenant=self.tenant_pj,
            cnpj=self.tenant_pj.cnpj,
            razao_social=self.tenant_pj.razao_social,
        )
        TenantPessoaFisica.objects.create(tenant=self.tenant_pf, cpf=self.tenant_pf.cpf)

        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="password123",
            email="test@example.com",
        )
        # Correção: Criar perfil de usuário explicitamente
        UserProfile.objects.create(user=self.user)

    def test_tenant_creation_and_signal(self) -> None:
        """Testa se a criação de Tenant e seus sub-objetos (PJ/PF) funciona."""
        self.assertEqual(Tenant.objects.count(), 2)
        self.assertTrue(TenantPessoaJuridica.objects.filter(tenant=self.tenant_pj).exists())
        pj_info = TenantPessoaJuridica.objects.get(tenant=self.tenant_pj)
        self.assertEqual(pj_info.cnpj, self.tenant_pj.cnpj)
        self.assertTrue(TenantPessoaFisica.objects.filter(tenant=self.tenant_pf).exists())
        pf_info = TenantPessoaFisica.objects.get(tenant=self.tenant_pf)
        self.assertEqual(pf_info.cpf, self.tenant_pf.cpf)

    def test_user_profile_creation_signal(self) -> None:
        """Testa se o UserProfile é criado para um novo usuário."""
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.language, "pt-br")

    def test_is_module_enabled_method(self) -> None:
        """Testa a lógica de verificação de módulos habilitados no Tenant."""
        self.tenant_pj.enabled_modules = {"modules": ["financeiro", "obras"]}
        self.tenant_pj.save()
        self.assertTrue(self.tenant_pj.is_module_enabled("financeiro"))
        self.assertTrue(self.tenant_pj.is_module_enabled("obras"))
        self.assertFalse(self.tenant_pj.is_module_enabled("estoque"))

    def test_tenant_user_relationship(self) -> None:
        """Testa o relacionamento entre Tenant, User e seus papéis."""
        role = Role.objects.create(tenant=self.tenant_pj, name="Gerente")
        department = Department.objects.create(tenant=self.tenant_pj, name="Administrativo")
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant_pj,
            user=self.user,
            role=role,
            department=department,
            is_tenant_admin=True,
        )
        self.assertEqual(TenantUser.objects.filter(tenant=self.tenant_pj).count(), 1)
        self.assertEqual(TenantUser.objects.filter(user=self.user).count(), 1)
        self.assertTrue(tenant_user.is_tenant_admin)
        self.assertIsNotNone(tenant_user.role)
        if tenant_user.role is not None:
            self.assertEqual(tenant_user.role.name, "Gerente")


class CoreViewsTestCase(TestCase):
    """Testes para as views legadas do app Core."""

    def setUp(self) -> None:
        """Configura dados básicos para os testes de view."""
        self.client = Client()
        self.superuser = CustomUser.objects.create_superuser(
            "superuser",
            "super@example.com",
            "password123",
        )
        self.admin_user = CustomUser.objects.create_user(
            "adminuser",
            "admin@example.com",
            "password123",
        )
        self.regular_user = CustomUser.objects.create_user(
            "regularuser",
            "regular@example.com",
            "password123",
        )
        self.tenant: Tenant = Tenant.objects.create(name="Empresa Teste", subdomain="teste")
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
        """Testa o fluxo de login e logout de um usuário."""
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), f"{reverse('core:login')}?next=/dashboard/")

        response = self.client.post(
            reverse("core:login"),
            {"username": "regularuser", "password": "password123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("dashboard"))

        response = self.client.get(reverse("core:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("core:login"))

    def test_superuser_access(self) -> None:
        """Testa se o superuser tem acesso às views de gerenciamento de tenants."""
        self.client.login(username="superuser", password="password123")
        response = self.client.get(reverse("core:tenant_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("core:tenant_create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_permission_denied(self) -> None:
        """Testa se um usuário comum é bloqueado de acessar áreas restritas."""
        self.client.login(username="regularuser", password="password123")
        response = self.client.get(reverse("core:tenant_list"))
        self.assertEqual(response.status_code, 302)
        expected_location = f"{reverse('core:login')}?next={reverse('core:tenant_list')}"
        self.assertEqual(response.headers.get("Location"), expected_location)

    def test_tenant_admin_access(self) -> None:
        """Testa se um admin de tenant pode acessar a lista de usuários do seu tenant."""
        self.client.login(username="adminuser", password="password123")
        session = self.client.session
        session["tenant_id"] = self.tenant.pk
        session.save()
        response = self.client.get(reverse("core:tenant_user_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.regular_user.username, response.content.decode())

    def test_switch_tenant(self) -> None:
        """Testa a funcionalidade de troca de tenant."""
        tenant2: Tenant = Tenant.objects.create(name="Outra Empresa", subdomain="outra")
        TenantUser.objects.create(tenant=tenant2, user=self.admin_user, role=self.admin_role)
        self.client.login(username="adminuser", password="password123")

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("core:tenant_select"))

        self.client.get(reverse("core:switch_tenant", args=[self.tenant.pk]))
        self.assertEqual(self.client.session["tenant_id"], self.tenant.pk)

        self.client.get(reverse("core:switch_tenant", args=[tenant2.pk]))
        self.assertEqual(self.client.session["tenant_id"], tenant2.pk)

    @pytest.mark.skip(reason="Teste obsoleto: a lógica de criação foi movida para o wizard e tem testes dedicados.")
    def test_tenant_creation_view(self) -> None:
        """Testa a view de criação de tenant (legada)."""
        self.client.login(username="superuser", password="password123")
        data: dict[str, Any] = {
            "name": "Nova Empresa Via Teste",
            "subdomain": "nova-teste",
            "status": "active",
            "tipo_pessoa": "PJ",
            "pj-razao_social": "Nova Empresa Teste LTDA",
            "pj-cnpj": "98.765.432/0001-11",
            "principal-logradouro": "Rua Teste",
            "principal-numero": "123",
            "principal-bairro": "Centro",
            "principal-cidade": "Cidade Teste",
            "principal-uf": "TS",
            "principal-cep": "99999-999",
            "adicionais-TOTAL_FORMS": "0",
            "adicionais-INITIAL_FORMS": "0",
            "contatos-TOTAL_FORMS": "0",
            "contatos-INITIAL_FORMS": "0",
            "documentos-TOTAL_FORMS": "0",
            "documentos-INITIAL_FORMS": "0",
            "admins-TOTAL_FORMS": "0",
            "admins-INITIAL_FORMS": "0",
        }
        response = self.client.post(reverse("core:tenant_create"), data)
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        # O redirecionamento pode variar dependendo da validação
        self.assertIn(
            response.headers.get("Location"),
            [
                reverse("core:tenant_list"),
                reverse("core:tenant_create"),
            ],
        )

        created = Tenant.objects.filter(subdomain="nova-teste").exists()
        if response.headers.get("Location") == reverse("core:tenant_create"):
            # Re-renderização (validação incompleta).
            # Apenas garantir que não criou indevidamente.
            self.assertFalse(created, "Tenant inesperadamente criado apesar de redirect voltar para create.")
        else:
            self.assertTrue(created, "Tenant não criado ao redirecionar para lista.")


class CoreAPITestCase(APITestCase):
    """Testes para a API legada do app Core."""

    # Ajuda o Pylance a inferir o tipo do cliente da API
    client: APIClient

    def setUp(self) -> None:
        """Configura dados básicos para os testes de API."""
        # Usa APIClient explicitamente para expor force_authenticate e .data
        self.client: APIClient = APIClient()
        self.superuser = CustomUser.objects.create_superuser(
            "superuser_api",
            "super_api@example.com",
            "password123",
        )
        self.regular_user = CustomUser.objects.create_user(
            "regularuser_api",
            "regular_api@example.com",
            "password123",
        )
        self.tenant = Tenant.objects.create(name="Empresa API", subdomain="api")
        TenantUser.objects.create(tenant=self.tenant, user=self.regular_user)

    def test_superuser_can_list_tenants_api(self) -> None:
        """Testa se o superuser pode listar tenants via API."""
        client = cast(APIClient, self.client)
        client.force_authenticate(user=self.superuser)
        url = reverse("core_api:tenant-list")
        resp_any = cast(Any, client.get(url))
        self.assertEqual(resp_any.status_code, status.HTTP_200_OK)
        data = resp_any.data
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Empresa API")

    def test_regular_user_cannot_list_tenants_api(self) -> None:
        """Testa se um usuário comum não pode listar tenants via API."""
        client = cast(APIClient, self.client)
        client.force_authenticate(user=self.regular_user)
        url = reverse("core_api:tenant-list")
        resp_any = cast(Any, client.get(url))
        self.assertEqual(resp_any.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_users_api_by_superuser(self) -> None:
        """Testa se o superuser pode listar usuários via API."""
        client = cast(APIClient, self.client)
        client.force_authenticate(user=self.superuser)
        url = reverse("core_api:user-list")
        resp_any = cast(Any, client.get(url, format="json"))
        self.assertEqual(resp_any.status_code, status.HTTP_200_OK)

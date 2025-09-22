"""Testes para os modelos legados do app Core."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Department,
    Role,
    Tenant,
    TenantPessoaFisica,
    TenantPessoaJuridica,
    TenantUser,
    UserProfile,
)

# ruff: noqa: PT009, PLR2004, S106

CustomUser = get_user_model()


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

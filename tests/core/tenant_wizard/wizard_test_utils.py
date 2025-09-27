"""Utilitários de teste para dirigir o wizard de criação/edição de Tenant.

Utilidades do wizard migradas como parte da
migração para a estrutura unificada de testes em ``tests/``. Todos os testes
devem agora importar via::

    from tests.core.tenant_wizard.wizard_test_utils import TenantWizardTestHelper
"""

from http import HTTPStatus

import pytest
from django.http import HttpResponse
from django.test.client import Client
from django.urls import reverse

from core.models import Tenant


class TenantWizardTestHelper:
    """Helper para dirigir o wizard multi-step de criação de Tenant em testes.

    Uso básico:
        helper = TenantWizardTestHelper(client)
        helper.start()
        helper.step1_pj(name="Empresa X", razao_social="Empresa X LTDA", cnpj="12.345.678/0001-90")
        helper.skip_steps(2, 4)
        helper.step5_config(subdomain="empresa-x", status="active")
        helper.skip_steps(6, 6)
        resp = helper.finish()
    """

    def __init__(self, client: Client) -> None:
        """Inicializa com uma instância de ``django.test.Client``."""
        self.client = client
        self.create_url = reverse("core:tenant_create")

    def start(self) -> HttpResponse:
        """Realiza o GET inicial do wizard e garante status 200."""
        r = self.client.get(self.create_url)
        if r.status_code != HTTPStatus.OK:
            pytest.fail(f"Falha GET inicial wizard: {r.status_code}")
        return r

    def step1_pj(
        self,
        *,
        name: str = "Empresa Teste Wizard",
        razao_social: str = "Empresa Teste Wizard LTDA",
        cnpj: str = "11.222.333/0001-44",
    ) -> HttpResponse:
        """Executa o passo 1 para pessoa jurídica (PJ) e valida redirect 302."""
        data = {
            "tipo_pessoa": "PJ",
            "pj-tipo_pessoa": "PJ",
            "pj-name": name,
            "pj-razao_social": razao_social,
            "pj-cnpj": cnpj,
        }
        r = self.client.post(self.create_url, data)
        if r.status_code != HTTPStatus.FOUND:
            pytest.fail(f"Step1 não redirecionou: {r.status_code}")
        return r

    def skip_steps(self, start_step: int, end_step: int) -> HttpResponse:
        """Avança steps enviando payload mínimo onde necessário.

        Observação: o Step 2 (Endereço) possui campos obrigatórios; portanto,
        para navegação livre é necessário enviar um payload mínimo válido. Os
        demais steps aceitam POST vazio por padrão.
        """
        last_resp: HttpResponse | None = None
        step_address = 2  # Step 2: Endereço (requer payload mínimo)
        current = start_step
        while current <= end_step:
            if current == step_address:
                data = {
                    "main-cep": "01000-000",
                    "main-logradouro": "Rua Teste",
                    "main-numero": "1",
                    "main-bairro": "Centro",
                    "main-cidade": "São Paulo",
                    "main-uf": "SP",
                    "main-pais": "Brasil",
                }
            else:
                data = {}

            last_resp = self.client.post(self.create_url, data)
            if last_resp.status_code != HTTPStatus.FOUND:
                pytest.fail(f"Skip step falhou: {last_resp.status_code}")
            current += 1

        if last_resp is None:
            pytest.fail("skip_steps recebeu intervalo vazio (start_step > end_step)")
        return last_resp

    def step5_config(self, subdomain: str | None = None, status: str | None = "active") -> HttpResponse:
        """Configura Step 5 com payload mínimo válido e valida redirect 302.

        Observação: O Step 5 possui diversos campos obrigatórios no ModelForm
        (timezone, idioma, moeda, plano, limites), que quando o form está
        bound (POST) precisam estar presentes para validar. Por isso enviamos
        um conjunto mínimo com valores padrão.
        """
        data: dict[str, object] = {
            # Campos mínimos obrigatórios
            "main-plano_assinatura": "BASIC",
            "main-max_usuarios": "5",
            "main-max_armazenamento_gb": "1",
            "main-timezone": "America/Sao_Paulo",
            "main-idioma_padrao": "pt-br",
            "main-moeda_padrao": "BRL",
            # Módulos (opcional, mas válido)
            "main-enabled_modules": ["admin"],
        }
        if subdomain is not None:
            data["main-subdomain"] = subdomain
        if status is not None:
            data["main-status"] = status
        r = self.client.post(self.create_url, data)
        if r.status_code != HTTPStatus.FOUND:
            pytest.fail(f"Step5 não redirecionou: {r.status_code}")
        return r

    def step5_config_expect_error(
        self,
        subdomain: str | None = None,
        status: str | None = "active",
    ) -> HttpResponse:
        """Versão do passo 5 que não exige redirect 302.

        Retorna o response bruto para que o teste possa validar mensagens/estado de erro.
        """
        data: dict[str, object] = {}
        if subdomain is not None:
            data["main-subdomain"] = subdomain
        if status is not None:
            data["main-status"] = status
        return self.client.post(self.create_url, data)

    def finish(self, *, confirmar: bool = True, termos: bool = True) -> HttpResponse:
        """Finaliza o wizard, marcando confirmações conforme parâmetros."""
        data: dict[str, object] = {"finish_wizard": "1"}
        if confirmar:
            data["main-confirmar_dados"] = "on"
        if termos:
            data["main-aceitar_termos"] = "on"
        return self.client.post(self.create_url, data)

    def tenant_exists(self, subdomain: str) -> bool:
        """Retorna True se existir Tenant com o subdomínio informado."""
        return Tenant.objects.filter(subdomain=subdomain).exists()

    def fast_full_creation(
        self,
        subdomain: str,
        *,
        name: str = "Empresa Fast",
        razao_social: str = "Empresa Fast LTDA",
        cnpj: str = "55.666.777/0001-88",
        status: str = "active",
    ) -> HttpResponse:
        """Fluxo completo resumido para criar Tenant PJ.

        Retorna o response final (redirect) do finish.
        """
        self.start()
        self.step1_pj(name=name, razao_social=razao_social, cnpj=cnpj)
        self.skip_steps(2, 4)
        self.step5_config(subdomain=subdomain, status=status)
        self.skip_steps(6, 6)
        return self.finish()

import pytest
from django.contrib.auth import get_user_model

from core.models import Tenant
from funcionarios.models import Funcionario
from user_management.forms import UsuarioUpdateForm
from user_management.models import PerfilUsuarioEstendido

User = get_user_model()


@pytest.mark.django_db
def test_cargo_salario_readonly_with_funcionario():
    tenant = Tenant.objects.create(nome="T", slug="t")
    u = User.objects.create_user("funcuser", password="x")
    perfil = PerfilUsuarioEstendido.objects.get(user=u)
    # Preencher campos obrigatórios do modelo Funcionario (cargo, sexo, salario_base, etc.)
    Funcionario.objects.create(
        tenant=tenant,
        user=u,
        nome_completo="Nome",
        cpf="000.000.000-00",
        data_nascimento="2000-01-01",
        sexo="M",
        data_admissao="2024-01-01",
        cargo="Analista",
        salario_base="1000.00",
    )
    form = UsuarioUpdateForm(instance=perfil)
    assert form.fields["cargo"].disabled is True
    assert form.fields["salario"].disabled is True

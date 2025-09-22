from typing import Any

from ..models import Contato, Endereco, EnderecoAdicional, Tenant, TenantUser


def build_tenant_snapshot(tenant: Tenant) -> dict[str, Any]:
    principal = Endereco.objects.filter(tenant=tenant, tipo="PRINCIPAL").first()
    adicionais = list(
        EnderecoAdicional.objects.filter(tenant=tenant).values("tipo", "logradouro", "numero", "cidade", "uf")
    )
    contatos = list(Contato.objects.filter(tenant=tenant).values("nome", "email", "telefone", "cargo"))
    admins = []
    for tu in TenantUser.objects.filter(tenant=tenant, is_tenant_admin=True).select_related("user", "role"):
        admins.append(
            {
                "email": tu.user.email,
                "ativo": tu.user.is_active,
                "cargo": tu.cargo,
                "role": tu.role.name if tu.role else None,
            }
        )
    return {
        "tenant": {
            "name": tenant.name,
            "tipo_pessoa": tenant.tipo_pessoa,
            "subdomain": tenant.subdomain,
        },
        "enderecos": {
            "principal": {
                "logradouro": principal.logradouro if principal else None,
                "cidade": principal.cidade if principal else None,
                "uf": principal.uf if principal else None,
            },
            "adicionais_count": len(adicionais),
        },
        "contatos_count": len(contatos),
        "admins": admins,
        "modules": sorted(
            tenant.enabled_modules.get("modules", []) if isinstance(tenant.enabled_modules, dict) else []
        ),
    }

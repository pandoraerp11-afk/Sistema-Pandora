import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora_erp.settings")


def main():
    django.setup()
    from core.models import Tenant
    from documentos.models import CategoriaDocumento, RegraDocumento, TipoDocumento

    cat, _ = CategoriaDocumento.objects.get_or_create(nome="Geral", defaults={"ordem": 1})
    t1, _ = TipoDocumento.objects.get_or_create(nome="Contrato Social", defaults={"categoria": cat})
    t2, _ = TipoDocumento.objects.get_or_create(
        nome="RG Representante", defaults={"categoria": cat, "periodicidade": "unico"}
    )

    tenant = Tenant.objects.first()
    regra_msgs = []
    if tenant:
        r1, c1 = RegraDocumento.objects.get_or_create(
            tipo=t1, escopo="tenant", tenant=tenant, defaults={"exigencia": "obrigatorio", "status": "aprovada"}
        )
        regra_msgs.append(f"Regra t1 {'criada' if c1 else 'existente'} id={r1.id}")
        r2, c2 = RegraDocumento.objects.get_or_create(
            tipo=t2, escopo="tenant", tenant=tenant, defaults={"exigencia": "opcional", "status": "aprovada"}
        )
        regra_msgs.append(f"Regra t2 {'criada' if c2 else 'existente'} id={r2.id}")
    else:
        regra_msgs.append("Nenhum tenant encontrado")

    print("Categoria:", cat.id, cat.nome)
    print("Tipos:", t1.id, t1.nome, "|", t2.id, t2.nome)
    print("Tenant:", getattr(tenant, "id", None))
    for m in regra_msgs:
        print(m)
    print("Seed concluído.")


if __name__ == "__main__":
    main()

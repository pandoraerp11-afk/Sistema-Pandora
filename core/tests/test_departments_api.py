from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.forms import RoleForm
from core.models import Department, Tenant

User = get_user_model()


@pytest.mark.django_db
def test_api_departments_list_variations(client):
    # Superuser login
    User.objects.create_superuser(username="admin", email="admin@example.com", password="pass")
    client.login(username="admin", password="pass")

    # Tenants
    t1 = Tenant.objects.create(name="Tenant A", subdomain="ta")
    t2 = Tenant.objects.create(name="Tenant B", subdomain="tb")

    # Departments: global + tenant specific
    d_global = Department.objects.create(name="Global Dep")
    d_t1 = Department.objects.create(name="Financeiro", tenant=t1)
    d_t2 = Department.objects.create(name="RH", tenant=t2)

    url = reverse("core:api_departments_list")

    # 1) Sem tenant => somente globais
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()["results"]
    ids = {d["id"] for d in data}
    assert d_global.id in ids and d_t1.id not in ids and d_t2.id not in ids

    # 2) Com tenant t1 + include_globals=true (default) => global + t1
    resp = client.get(url, {"tenant": t1.id})
    assert resp.status_code == 200
    data = resp.json()["results"]
    names = {d["name"] for d in data}
    assert "Global Dep" in names and "Financeiro" in names and "RH" not in names

    # 3) Com tenant t1 + include_globals=false => apenas t1
    resp = client.get(url, {"tenant": t1.id, "include_globals": "false"})
    assert resp.status_code == 200
    data = resp.json()["results"]
    names = {d["name"] for d in data}
    assert "Financeiro" in names and "Global Dep" not in names and "RH" not in names


@pytest.mark.django_db
def test_role_form_department_queryset_superuser_filters_by_selected_tenant():
    user = User.objects.create_superuser(username="admin2", email="admin2@example.com", password="pass")
    t1 = Tenant.objects.create(name="Tenant X", subdomain="tx")
    t2 = Tenant.objects.create(name="Tenant Y", subdomain="ty")
    Department.objects.create(name="Global Dep")
    Department.objects.create(name="Operações", tenant=t1)
    Department.objects.create(name="Comercial", tenant=t2)

    request = SimpleNamespace(user=user)

    # Sem tenant selecionado -> todos (globais + específicos)
    form_all = RoleForm(request=request, data={})
    names_all = {d.name for d in form_all.fields["department"].queryset}
    assert {"Global Dep", "Operações", "Comercial"}.issubset(names_all)

    # Com tenant t1 selecionado
    form_t1 = RoleForm(request=request, data={"tenant": str(t1.id)})
    names_t1 = {d.name for d in form_t1.fields["department"].queryset}
    assert "Global Dep" in names_t1 and "Operações" in names_t1 and "Comercial" not in names_t1

    # Com tenant t2 selecionado
    form_t2 = RoleForm(request=request, data={"tenant": str(t2.id)})
    names_t2 = {d.name for d in form_t2.fields["department"].queryset}
    assert "Global Dep" in names_t2 and "Comercial" in names_t2 and "Operações" not in names_t2

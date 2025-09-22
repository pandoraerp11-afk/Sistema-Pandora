import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora_erp.settings")
import django

django.setup()
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import RequestFactory

from core.forms import RoleForm

rf = RequestFactory()
User = get_user_model()
user = User.objects.filter(is_superuser=True).first()
req = rf.get("/")
req.user = user
form = RoleForm(request=req)
ctx = {"form": form, "object": None, "model_name": "Cargo"}
html = get_template("core/role_form.html").render(ctx, request=req)
import re

m = re.search(r'<script id="permData".*?>([\s\S]*?)</script>', html)
print("Template user superuser?", bool(user and user.is_superuser))
print("permData found:", bool(m))
if m:
    snippet = m.group(1).strip()[:1000]
    print("permData snippet (first 1000 chars):")
    print(snippet)
    print("\nStarts with [ ?", snippet.lstrip().startswith("["))
    print("Ends with ] ?", snippet.rstrip().endswith("]"))
else:
    open("dump_role_form.html", "w", encoding="utf-8").write(html)
    print("Full HTML dumped to dump_role_form.html")

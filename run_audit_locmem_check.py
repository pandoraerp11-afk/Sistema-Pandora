import io
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora_erp.settings")
django.setup()
from django.core.cache import cache
from django.core.management import call_command

cache.set("module_deny_count:clientes", 7, 60)
cache.set("module_deny_count:fornecedores", 3, 60)
out = io.StringIO()
call_command("audit_auth", stdout=out)
print("OUTPUT_START")
print(out.getvalue())
print("OUTPUT_END")

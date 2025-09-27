"""Teste de concorrência de geração de subdomínios.

Concorrência de criação de subdomínio.
Import legacy eliminado.
"""

import threading
import time
from collections import Counter

import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError, connections

from core.models import Tenant

pytestmark = [pytest.mark.django_db]
User = get_user_model()


def test_subdomain_concurrency_generation() -> None:
    """Verifica geração concorrente de subdomínios com retry simples para SQLite.

    Reduzido para menor complexidade ciclomática: lógica linear + loop + único ponto
    de verificação de erro por worker.
    """
    base = "empresa"
    results: list[str] = []
    errors: list[Exception] = []

    engine = connections["default"].settings_dict.get("ENGINE", "")
    thread_count = 20 if "postgres" in engine else 6  # reduzir para SQLite
    lock_phrase = "locked"
    lock_max_attempts = 6

    def worker(i: int) -> None:
        sub = f"{base}-{i}"
        created = False
        for attempt in range(lock_max_attempts):
            try:
                Tenant.objects.create(name=f"Emp {i}", subdomain=sub)
            except OperationalError as exc:  # pragma: no cover
                if lock_phrase in str(exc).lower() and attempt < lock_max_attempts - 1:
                    time.sleep(0.02 * (attempt + 1))
                    continue
                errors.append(exc)
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
                break
            else:
                results.append(sub)
                created = True
                break
        if not created and (not errors or sub not in str(errors[-1])):
            errors.append(RuntimeError(f"Falha ao criar subdomínio {sub}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Se houve qualquer erro, falhar explicitamente mostrando a lista
    assert not errors, f"Erros durante criação concorrente: {errors}"

    counts = Counter(results)
    # Garantir quantidade esperada e ausência de duplicações
    assert len(results) == thread_count
    assert all(v == 1 for v in counts.values())


# Fim do arquivo: import legacy removido.

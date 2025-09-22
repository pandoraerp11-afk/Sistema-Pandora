#!/usr/bin/env python
"""Hook pre-commit: falha se scripts obsoletos reaparecerem.
Considera também arquivos vazios (0 bytes).
"""

from __future__ import annotations

import sys
from pathlib import Path

LEGACY = [
    "parse_ci.py",
    "limpar_migracoes.py",
    "_clean_caches.py",
    "tmp_list_tu.py",
    "sitecustomize.py",
    "TESTES_ORGANIZACAO.md",  # duplicado deve existir só em docs/
    "docs/TEST_GUIDELINES.md",  # unificado no guia principal, não recriar
]

root = Path(__file__).resolve().parents[2]
found = []
for name in LEGACY:
    p = root / name
    if p.exists():
        size = p.stat().st_size
        try:
            if size == 0:
                # auto-remover vazio para reduzir ruído
                p.unlink()
                continue
        except Exception:
            pass
        found.append(f"{name} (size={size})")

if found:
    print("[forbid-legacy-scripts] Encontrado(s):", ", ".join(found))
    print("Remova estes arquivos. São obsoletos.")
    sys.exit(1)

sys.exit(0)

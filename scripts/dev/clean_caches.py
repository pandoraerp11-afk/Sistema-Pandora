"""Limpa caches e artefatos de build/testes.
Uso:
  python scripts/dev/clean_caches.py
"""

import contextlib
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # raiz do backend
TARGETS = [".pytest_cache", ".mypy_cache", ".ruff_cache", ".coverage", ".cache"]

removed = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    if "__pycache__" in dirnames:
        p = Path(dirpath) / "__pycache__"
        shutil.rmtree(p, ignore_errors=True)
        removed.append(str(p))

for t in TARGETS:
    p = ROOT / t
    if p.exists():
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            with contextlib.suppress(Exception):
                p.unlink()
        removed.append(str(p))

pyc_count = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    for f in filenames:
        if f.endswith(".pyc"):
            try:
                os.remove(os.path.join(dirpath, f))
                pyc_count += 1
            except Exception:
                pass

print("REMOVIDOS_DIRS_OU_ARQUIVOS:", len(removed))
print("ARQUIVOS_PYC_REMOVIDOS:", pyc_count)

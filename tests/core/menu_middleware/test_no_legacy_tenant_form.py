import glob
import os
from pathlib import Path


def test_no_legacy_tenant_form_template_present():
    base_dir = Path(__file__).resolve().parents[2]  # raiz do backend
    matches = []
    # Procurar qualquer arquivo que corresponda a tenant_form*.html
    for pattern in ["**/tenant_form.html", "**/tenant_form_*.html", "**/*tenant_form*.html"]:
        matches.extend(glob.glob(str(base_dir / pattern), recursive=True))
    # Filtrar falsos positivos (comentários capturados não contam, apenas arquivos reais)
    real_files = [m for m in matches if os.path.isfile(m)]
    assert not real_files, f"Templates legacy tenant_form ainda presentes: {real_files}"

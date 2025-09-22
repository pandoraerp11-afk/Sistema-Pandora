import glob
from pathlib import Path


def test_reserved_subdomains_defined_only_once():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for m in glob.glob(str(root / "**" / "*.py"), recursive=True):
        # Ignorar este próprio arquivo de teste
        if m.endswith("test_subdomain_constants_sync.py"):
            continue
        with open(m, encoding="utf-8") as fh:
            text = fh.read()
            # Garantir match somente de declaração real (início de linha, evitando comentários inline)
            for line in text.splitlines():
                if line.strip().startswith("RESERVED_SUBDOMAINS") and "=" in line:
                    offenders.append(m)
                    break
    # Deve existir exatamente UMA declaração (em validators.py)
    if len(offenders) == 1 and offenders[0].endswith("validators.py"):
        return
    assert not offenders, f"RESERVED_SUBDOMAINS redeclarado em: {offenders}"

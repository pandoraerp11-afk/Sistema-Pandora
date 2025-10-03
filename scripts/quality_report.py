"""Gera relatórios de qualidade (Ruff + Mypy) e um sumário estruturado.

Uso (exemplos no Windows PowerShell):
    python scripts/quality_report.py
    python scripts/quality_report.py --ruff-output relatorio_ruff.txt --mypy-output relatorio_mypy.txt

O script:
1. Executa `ruff check .` e salva a saída bruta.
2. Executa `mypy .` conforme configuração do pyproject.toml.
3. Cria um JSON de sumário com contagem por código de erro (Ruff) e por tipo (Mypy).
4. Nao altera código - apenas coleta métricas para permitir correções graduais.

Objetivo: evitar aplicar correções massivas de uma vez reduzindo risco de impacto em regras de negócio.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


RUFF_LINE_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z0-9]+) .+")
MYPY_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<severity>error|note): (?P<msg>.+?)  \[(?P<code>[^\]]+)\]",
)


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Executa comando seguro (lista interna) capturando stdout/stderr.

    Não usa shell e só recebe lista construída pelo script. Retorna
    (codigo_saida, stdout, stderr).
    """
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)  # noqa: S603
    return proc.returncode, proc.stdout, proc.stderr


def generate_ruff_report(output_path: Path) -> tuple[dict[str, int], str | None]:
    """Roda Ruff e retorna (contagem_por_codigo, mensagem_status).

    Mensagem_status é apenas informativa quando há findings ou erro de execução.
    """
    if shutil.which("ruff") is None:
        return {}, "ruff não encontrado no PATH. Instale com: pip install ruff"
    code, out, err = run_cmd([sys.executable, "-m", "ruff", "check", "."])
    raw = out or err
    output_path.write_text(raw, encoding="utf-8")
    counter: Counter[str] = Counter()
    for line in raw.splitlines():
        m = RUFF_LINE_RE.match(line.strip())
        if m:
            counter[m.group("code")] += 1
    return dict(counter), None if code == 0 else f"ruff retornou código {code} (há findings)"


def generate_mypy_report(output_path: Path) -> tuple[dict[str, int], str | None]:
    """Roda Mypy e retorna (contagem_por_codigo, mensagem_status)."""
    if shutil.which("mypy") is None:
        return {}, "mypy não encontrado no PATH. Instale com: pip install mypy"
    code, out, err = run_cmd([sys.executable, "-m", "mypy", "."])
    text = out or err
    output_path.write_text(text, encoding="utf-8")
    counter: Counter[str] = Counter()
    for line in text.splitlines():
        m = MYPY_LINE_RE.match(line.strip())
        if m:
            counter[m.group("code")] += 1
    return dict(counter), None if code == 0 else f"mypy retornou código {code} (há findings)"


def group_ruff_categories(code_counts: dict[str, int]) -> dict[str, int]:
    """Agrupa códigos Ruff por prefixo/letra para visão macro."""
    grouped: dict[str, int] = defaultdict(int)
    for code, count in code_counts.items():
        prefix = re.match(r"^[A-Z]+", code)
        cat = prefix.group(0) if prefix else code[:1]
        grouped[cat] += count
    return dict(grouped)


def main() -> None:
    """Ponto de entrada do gerador de relatórios de qualidade."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ruff-output", default="relatorio_ruff.txt")
    parser.add_argument("--mypy-output", default="relatorio_mypy.txt")
    parser.add_argument("--summary-json", default="quality_summary.json")
    args = parser.parse_args()

    ruff_path = ROOT / args.ruff_output
    mypy_path = ROOT / args.mypy_output
    summary_path = ROOT / args.summary_json

    logger = logging.getLogger("quality")
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    logger.info("Gerando relatório Ruff...")
    ruff_counts, ruff_msg = generate_ruff_report(ruff_path)
    logger.info("Gerando relatório Mypy...")
    mypy_counts, mypy_msg = generate_mypy_report(mypy_path)

    summary: dict[str, Any] = {
        "ruff_counts": ruff_counts,
        "ruff_grouped": group_ruff_categories(ruff_counts),
        "mypy_counts": mypy_counts,
        "messages": {"ruff": ruff_msg, "mypy": mypy_msg},
        "paths": {
            "ruff": str(ruff_path),
            "mypy": str(mypy_path),
        },
    }

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Sumário salvo em: %s", summary_path)
    if ruff_msg:
        logger.warning("Ruff: %s", ruff_msg)
    if mypy_msg:
        logger.warning("Mypy: %s", mypy_msg)

    top_ruff = sorted(ruff_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    logger.info("Top Ruff codes: %s", ", ".join(f"{c}:{n}" for c, n in top_ruff) or "(vazio)")
    logger.info("Total códigos mypy distintos: %d", len(mypy_counts))

    logger.info("Ordem sugerida de correção segura (batch):")
    logger.info("  1. Imports (I, F401) - auto-fix seguro")
    logger.info("  2. Unused vars (F841) - revisar antes de remover para não mascarar lógica")
    logger.info("  3. Simplificações (UP, SIM) - aplicar seletivamente em services menos críticos")
    logger.info("  4. Potenciais bugs (B) - analisar caso a caso")
    logger.info("  5. PL* - somente após estabilizar passos anteriores")


if __name__ == "__main__":  # pragma: no cover
    main()

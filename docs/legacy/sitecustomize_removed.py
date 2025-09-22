"""Arquivo original sitecustomize.py movido.

Mantido apenas para histórico da supressão de warning DRF.
Remoção efetiva em favor de limpeza de bootstrap.
"""

CODE = r"""warnings.filterwarnings(
    'ignore',
    message=r\"Converter 'drf_format_suffix' is already registered.*\",
    category=_R,
)"""

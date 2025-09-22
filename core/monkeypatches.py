"""Monkeypatches centralizados.

1. URLField assume_scheme='https' por padrão (remove necessidade do
   FORMS_URLFIELD_ASSUME_HTTPS transitório e elimina RemovedInDjango60Warning).
2. widget_tweaks: evita DeprecationWarning do Python 3.13 sobre argumento
   posicional 'maxsplit' ao envolver re.split e reenviar com keyword.

Seguros porque:
- URLField: só define assume_scheme se não fornecido explicitamente.
- widget_tweaks: wrapper mínimo sem alterar semântica.
"""

from django.db.models import URLField as _URLField

# ---------------------------------------------------------------------------
# 1. URLField assume_scheme default
# ---------------------------------------------------------------------------
_original_urlfield_formfield = _URLField.formfield


def _urlfield_formfield(self, **kwargs):  # type: ignore[override]
    kwargs.setdefault("assume_scheme", "https")
    return _original_urlfield_formfield(self, **kwargs)


_URLField.formfield = _urlfield_formfield  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 2. widget_tweaks DeprecationWarning shim (escopo restrito)
# ---------------------------------------------------------------------------
"""Evita DeprecationWarning do Python 3.13 apenas dentro de widget_tweaks.

Em vez de substituir re.split globalmente (potencialmente surpreendendo
outras libs), importamos o módulo de template tags do widget_tweaks e
ajustamos apenas a função re.split referenciada lá.
"""
try:  # pragma: no cover - tolerante se lib não instalada
    import re as _re
    from importlib import import_module as _import_module

    _wt_mod = _import_module("widget_tweaks.templatetags.widget_tweaks")
    # Evitar patch duplicado
    if getattr(_wt_mod.re.split, "__name__", "") != "_wt_split_shim":
        _original_re_split = _re.split

        def _wt_split_shim(pattern, string, maxsplit=0, flags=0):
            return _original_re_split(pattern, string, maxsplit=maxsplit, flags=flags)

        _wt_mod.re.split = _wt_split_shim  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

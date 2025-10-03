from __future__ import annotations

from typing import Any, TypeVar

from django.db.models import Model, QuerySet

T = TypeVar("T", bound=Model)


class AdvancedPermissionManager:
    """
    Implementação mínima baseada no sistema padrão de permissões do Django.

    Objetivo: fornecer uma API estável para chamadas existentes sem alterar regras
    de negócio. Usa `user.has_perm("app_label.codename", obj)` quando possível.
    """

    @staticmethod
    def get_objects_for_user_with_permission(user: Any, model: type[T], perm_codename: str) -> QuerySet[T]:
        """
        Retorna todos os objetos do `model` se o usuário possuir a permissão
        declarada (nível de modelo). Caso contrário, retorna `none()`.
        """
        if getattr(user, "is_superuser", False):
            return model.objects.all()

        app_label = getattr(getattr(model, "_meta", None), "app_label", None) or ""
        perm_full = f"{app_label}.{perm_codename}" if app_label else perm_codename

        try:
            allowed = bool(user.has_perm(perm_full))
        except Exception:
            allowed = False

        return model.objects.all() if allowed else model.objects.none()

    @staticmethod
    def check_user_permission(user: Any, permission_codename: str, obj: Model | None = None) -> bool:
        """
        Verifica uma permissão arbitrária. Se `obj` for fornecido, tenta
        usar `app_label` do objeto. Aceita tanto "app.codename" quanto apenas
        "codename" (neste caso, deduz de `obj` quando possível).
        """
        if getattr(user, "is_superuser", False):
            return True

        if obj is not None:
            app_label = getattr(getattr(obj, "_meta", None), "app_label", None) or ""
            perm_full = permission_codename if "." in permission_codename else f"{app_label}.{permission_codename}"
            try:
                return bool(user.has_perm(perm_full, obj))
            except Exception:
                return False

        # Sem objeto: tenta como fornecido; se não vier com app, usa direto.
        perm_full = permission_codename
        try:
            return bool(user.has_perm(perm_full))
        except Exception:
            return False


class ModulePermissions:
    """
    Estrutura de permissões por módulo para comandos de setup.
    Mantida mínima de propósito; pode ser expandida conforme necessidade.
    Exemplo de formato:
        MODULE_PERMISSIONS = {
            "clientes": [("view_cliente", "Pode ver clientes")],
        }
    """

    MODULE_PERMISSIONS: dict[str, list[tuple[str, str]]] = {}

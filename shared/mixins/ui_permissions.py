from django.views.generic.base import ContextMixin

from core.utils import get_current_tenant
from shared.services.ui_permissions import build_ui_permissions


class UIPermissionsMixin(ContextMixin):
    """Mixin para disponibilizar `perms` no contexto do template padronizado.

    Configure um dos conjuntos abaixo:
      - module_key: ex. 'COTACAO' (usa PermissionResolver: VIEW_/CREATE_/EDIT_/DELETE_)
      - app_label + model_name: ex. 'cotacoes' + 'cotacao' (usa permissões Django no Role)
    """

    module_key: str | None = None
    app_label: str | None = None
    model_name: str | None = None
    resource: str | None = None

    def get_module_key(self) -> str | None:
        return self.module_key

    def get_app_label(self) -> str | None:
        return self.app_label

    def get_model_name(self) -> str | None:
        return self.model_name

    def get_resource(self) -> str | None:
        return self.resource

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_current_tenant(self.request)
        ui_perms = build_ui_permissions(
            self.request.user,
            tenant,
            module_key=self.get_module_key(),
            app_label=self.get_app_label(),
            model_name=self.get_model_name(),
            resource=self.get_resource(),
        )
        # Evitar conflitar com 'perms' do Django; expor como 'ui_perms'
        context.setdefault("ui_perms", ui_perms)
        context.setdefault("perms_ui", ui_perms)
        return context

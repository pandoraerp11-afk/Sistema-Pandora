from django.apps import AppConfig


class UserManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user_management"
    verbose_name = "Gerenciamento de Usuários"

    def ready(self):
        pass

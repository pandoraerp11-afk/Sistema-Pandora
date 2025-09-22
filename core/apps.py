from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """
        Importa os signals quando a aplicação está pronta.
        Isso garante que todos os signals sejam registrados corretamente.
        """

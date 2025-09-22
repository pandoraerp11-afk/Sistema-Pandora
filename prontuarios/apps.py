from django.apps import AppConfig


class ProntuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prontuarios"
    verbose_name = "Prontuários Médicos/Estéticos"

    def ready(self):
        """
        Método executado quando o app está pronto.
        Registra os signals e outras configurações.
        """

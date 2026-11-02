from django.apps import AppConfig


class HotelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hotel'

    def ready(self):
        # Conecta las señales de inicio y cierre de sesión
        from . import signals  # noqa: F401
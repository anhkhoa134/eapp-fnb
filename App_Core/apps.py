from django.apps import AppConfig


class AppCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_Core'

    def ready(self):
        from App_Core.audit import connect_signals

        connect_signals()

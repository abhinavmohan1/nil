from django.apps import AppConfig


class BbbIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bbb_integration'

    def ready(self):
        import importlib
        importlib.import_module('bbb_integration.signals')
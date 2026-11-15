from django.apps import AppConfig


class MicmodBaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'micmod_base'

    def ready(self):
        from . import pricing_v2_signals  # noqa: F401; register version-specific hooks

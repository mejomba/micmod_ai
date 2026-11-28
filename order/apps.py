from django.apps import AppConfig


class OrderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'order'

    def ready(self):
        import order.signals
        from .scheduling_adapters import register_bindings
        register_bindings()
        from .scheduling_events import connect
        connect()

from django.apps import AppConfig


class BusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bus'
    label = 'bus'
    verbose_name = 'Bus Tickets'

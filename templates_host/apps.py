"""
Templates Host App Configuration
(Renamed from 'templates' to avoid conflict with Django template system)
"""

from django.apps import AppConfig


class TemplatesHostConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'templates_host'
    verbose_name = 'Framework Templates'
    
    def ready(self):
        """
        Import signals or perform startup tasks here
        """
        # Import signals if you have any
        # from . import signals
        pass
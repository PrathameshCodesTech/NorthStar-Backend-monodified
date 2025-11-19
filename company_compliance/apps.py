"""
Company Compliance App Configuration
"""

from django.apps import AppConfig


class CompanyComplianceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'company_compliance'
    verbose_name = 'Company Compliance'
    
    def ready(self):
        """
        Import signals or perform startup tasks here
        """
        # Import signals if you have any
        # from . import signals
        pass
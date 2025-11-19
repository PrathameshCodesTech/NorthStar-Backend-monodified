from django.apps import AppConfig


class TenantManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenant_management'
    verbose_name = 'Tenant Management'
    
    def ready(self):
        """Load tenant databases when Django starts"""
        # Only load in main process, not in migrations
        import sys
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            try:
                from .tenant_utils import load_all_tenant_databases
                load_all_tenant_databases()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not load tenant databases: {e}")
"""
Multi-Tenant Database Router with Middleware
Automatically routes queries to correct tenant database based on context
Supports both SCHEMA and DATABASE isolation modes
"""

from django.conf import settings
import threading
import contextlib
from contextvars import ContextVar
import logging


logger = logging.getLogger(__name__)


# Use ContextVar for async-safe tenant context
_tenant_context: ContextVar[str] = ContextVar('tenant_context', default=None)


# Fallback thread-local for backwards compatibility
_thread_locals = threading.local()


def get_current_tenant():
    """Get current tenant from context (async-safe)"""
    # Try ContextVar first (async-safe)
    tenant = _tenant_context.get(None)
    if tenant:
        return tenant
    
    # Fallback to thread-local
    thread_tenant = getattr(_thread_locals, 'tenant', None)
    if thread_tenant:
        return thread_tenant
    
    # Last resort: try to get from current request (if in view context)
    try:
        from django.http import HttpRequest
        import inspect
        
        # Walk up the call stack to find request object
        for frame_info in inspect.stack():
            frame_locals = frame_info.frame.f_locals
            if 'request' in frame_locals:
                request = frame_locals['request']
                if isinstance(request, HttpRequest) and hasattr(request, 'tenant_slug'):
                    return request.tenant_slug
    except:
        pass
    
    return None


def set_current_tenant(tenant_slug):
    """Set current tenant in context (async-safe)"""
    if tenant_slug:
        # Validate tenant_slug format
        import re
        if not re.match(r'^[a-z0-9-]{3,50}$', tenant_slug):
            logger.warning(f"Invalid tenant_slug format: {tenant_slug}")
            return False
        
        _tenant_context.set(tenant_slug)
        _thread_locals.tenant = tenant_slug  # Fallback
        logger.debug(f"Set tenant context: {tenant_slug}")
        return True
    return False


def clear_current_tenant():
    """Clear current tenant from context (async-safe)"""
    current = get_current_tenant()
    if current:
        logger.debug(f"Clearing tenant context: {current}")
    
    _tenant_context.set(None)
    if hasattr(_thread_locals, 'tenant'):
        delattr(_thread_locals, 'tenant')


@contextlib.contextmanager
def tenant_context(tenant_slug):
    """Context manager for safe tenant switching"""
    previous_tenant = get_current_tenant()
    if set_current_tenant(tenant_slug):
        try:
            yield tenant_slug
        finally:
            if previous_tenant:
                set_current_tenant(previous_tenant)
            else:
                clear_current_tenant()
    else:
        # Invalid tenant_slug, don't switch context
        yield None


class ComplianceRouter:
    """
    Database router for multi-tenant compliance system
    
    Routing Rules:
    - templates_host app models → main database (default)
    - company_compliance app models → tenant database/schema
    - tenant_management models → main database (default)
    - user_management models → main database (default)
    
    Supports both DATABASE and SCHEMA isolation modes
    """
    
    def db_for_read(self, model, **hints):
        """Determine which database to read from with validation"""
        
        # System apps always use main database
        if model._meta.app_label in ['templates_host', 'tenant_management', 'user_management', 
                                       'auth', 'contenttypes', 'sessions', 'admin']:
            return 'default'
        
        # Company compliance models use tenant database/schema
        if model._meta.app_label == 'company_compliance':
            tenant = get_current_tenant()
            if tenant:
                connection_name = f"{tenant}_compliance_db"
                
                # Validate that the database connection exists
                from django.db import connections
                if connection_name in connections.databases:
                    logger.debug(f"Routing {model.__name__} to {connection_name}")
                    return connection_name
                else:
                    logger.error(f"Tenant connection {connection_name} not found!")
                    # For now, fall back to default (with warning)
                    logger.warning(f"Falling back to default database for {model.__name__}")
                    return 'default'
            
            # No tenant context - fall back with warning
            logger.warning(f"No tenant context for company_compliance model: {model.__name__}")
            return 'default'
        
        # Everything else uses main database
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Determine which database to write to"""
        return self.db_for_read(model, **hints)
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects in the same database
        
        CRITICAL: Must allow all relations within company_compliance app
        since all models are in the same tenant schema/database
        """
        
        # Allow all relations within company_compliance app
        if obj1._meta.app_label == 'company_compliance' and obj2._meta.app_label == 'company_compliance':
            return True
        
        # Allow relations within templates_host app
        if obj1._meta.app_label == 'templates_host' and obj2._meta.app_label == 'templates_host':
            return True
        
        # Allow relations within tenant_management app
        if obj1._meta.app_label == 'tenant_management' and obj2._meta.app_label == 'tenant_management':
            return True
        
        # Allow relations within user_management app
        if obj1._meta.app_label == 'user_management' and obj2._meta.app_label == 'user_management':
            return True
        
        # Allow relations within same app (general case)
        if obj1._meta.app_label == obj2._meta.app_label:
            return True
        
        # Default - let Django decide
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Determine which apps can migrate to which databases"""
        
        # Main database: system apps
        if db == 'default':
            return app_label in [
                'templates_host',
                'tenant_management', 
                'user_management',
                'auth',
                'contenttypes',
                'sessions',
                'admin',
                'messages',
                'authtoken',
            ]
        
        # Tenant databases/schemas: only company_compliance app
        if db.endswith('_compliance_db'):
            return app_label == 'company_compliance'
        
        # Deny migration for unknown databases
        return False
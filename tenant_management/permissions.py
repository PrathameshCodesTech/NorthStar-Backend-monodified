"""
Custom permissions for tenant management
"""

from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """
    Only Django superusers can access
    Used for tenant provisioning, plan management
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsSuperAdminOrReadOnly(BasePermission):
    """
    SuperAdmin can do anything, others can only read
    """
    
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_superuser


class CanManageTenants(BasePermission):
    """
    Check if user can manage tenants
    For future: when we have platform admins (not just superusers)
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # For now, only superusers
        if request.user.is_superuser:
            return True
        
        # Future: Check for platform admin role
        # return request.user.groups.filter(name='Platform Admins').exists()
        
        return False


# ============================================================================
# SUBSCRIPTION PLAN FEATURE PERMISSIONS
# ============================================================================

class CanCustomizeControls(BasePermission):
    """
    Permission to check if tenant's plan allows control customization
    
    - BASIC plan: Cannot customize (returns False)
    - PROFESSIONAL plan: Can customize controls (returns True)
    - ENTERPRISE plan: Can customize controls (returns True)
    
    Used in company_compliance views for control editing
    """
    message = "Control customization requires Professional or Enterprise plan. Please upgrade."
    
    def has_permission(self, request, view):
        # Allow GET requests for all plans
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Get tenant from request
        from core.database_router import get_current_tenant
        tenant_slug = get_current_tenant()
        
        if not tenant_slug:
            return False
        
        try:
            from .models import TenantDatabaseInfo
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            # Check if plan allows customization
            return tenant.subscription_plan.can_customize_controls
            
        except TenantDatabaseInfo.DoesNotExist:
            return False
    
    def has_object_permission(self, request, view, obj):
        # Allow GET requests
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # For modifications, check plan permission
        return self.has_permission(request, view)


class CanCreateCustomFrameworks(BasePermission):
    """
    Permission to check if tenant's plan allows creating custom frameworks
    
    - BASIC plan: Cannot create (returns False)
    - PROFESSIONAL plan: Cannot create (returns False)
    - ENTERPRISE plan: Can create (returns True)
    
    Used for:
    - Creating frameworks from scratch
    - Adding/removing controls from frameworks
    - Modifying framework structure
    """
    message = "Creating custom frameworks requires Enterprise plan. Please upgrade."
    
    def has_permission(self, request, view):
        # Allow GET/LIST for all plans
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Check for creation/modification methods
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            from core.database_router import get_current_tenant
            tenant_slug = get_current_tenant()
            
            if not tenant_slug:
                return False
            
            try:
                from .models import TenantDatabaseInfo
                tenant = TenantDatabaseInfo.objects.get(
                    tenant_slug=tenant_slug,
                    is_active=True
                )
                
                # Check if plan allows custom framework creation
                return tenant.subscription_plan.can_create_custom_frameworks
                
            except TenantDatabaseInfo.DoesNotExist:
                return False
        
        return True


class HasAPIAccess(BasePermission):
    """
    Permission to check if tenant's plan has API access
    
    - BASIC plan: No API access (returns False)
    - PROFESSIONAL plan: No API access (returns False)
    - ENTERPRISE plan: Full API access (returns True)
    
    Apply to API endpoints that should only be available to Enterprise
    Example: External integrations, webhooks, programmatic access
    """
    message = "API access requires Enterprise plan. Please upgrade or use the web interface."
    
    def has_permission(self, request, view):
        # Get tenant from request
        from core.database_router import get_current_tenant
        tenant_slug = get_current_tenant()
        
        if not tenant_slug:
            # If no tenant in context, might be superadmin - allow
            return request.user.is_superuser if hasattr(request, 'user') else False
        
        try:
            from .models import TenantDatabaseInfo
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            # Check if plan has API access
            return tenant.subscription_plan.has_api_access
            
        except TenantDatabaseInfo.DoesNotExist:
            return False


class HasAdvancedReporting(BasePermission):
    """
    Permission to check if tenant's plan has advanced reporting features
    
    - BASIC plan: Basic reports only (returns False)
    - PROFESSIONAL plan: Basic reports only (returns False)
    - ENTERPRISE plan: Advanced reports (returns True)
    
    Used for:
    - Custom report generation
    - Compliance dashboards
    - Export to multiple formats
    - Scheduled reports
    """
    message = "Advanced reporting requires Enterprise plan. Please upgrade."
    
    def has_permission(self, request, view):
        from core.database_router import get_current_tenant
        tenant_slug = get_current_tenant()
        
        if not tenant_slug:
            return False
        
        try:
            from .models import TenantDatabaseInfo
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            # Check if plan has advanced reporting
            return tenant.subscription_plan.has_advanced_reporting
            
        except TenantDatabaseInfo.DoesNotExist:
            return False


class HasSSOAccess(BasePermission):
    """
    Permission to check if tenant's plan has SSO (Single Sign-On) support
    
    - BASIC plan: No SSO (returns False)
    - PROFESSIONAL plan: No SSO (returns False)
    - ENTERPRISE plan: SSO enabled (returns True)
    
    Used for:
    - SAML authentication
    - OAuth integrations
    - Azure AD / Okta / Google Workspace SSO
    """
    message = "SSO (Single Sign-On) requires Enterprise plan. Please upgrade."
    
    def has_permission(self, request, view):
        from core.database_router import get_current_tenant
        tenant_slug = get_current_tenant()
        
        if not tenant_slug:
            return False
        
        try:
            from .models import TenantDatabaseInfo
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            # Check if plan has SSO
            return tenant.subscription_plan.has_sso
            
        except TenantDatabaseInfo.DoesNotExist:
            return False
        
class AllowUnauthenticatedRead(BasePermission):
    """
    Allow unauthenticated GET requests (for signup flow)
    Require authentication for modifications
    """
    
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True  # Allow anyone to read plans
        return request.user and request.user.is_authenticated and request.user.is_superuser


class AllowTenantCreation(BasePermission):
    """
    Allow unauthenticated POST for tenant creation (signup flow)
    Require superadmin for all other operations
    """
    
    def has_permission(self, request, view):
        # Allow unauthenticated POST for tenant creation
        if request.method == 'POST' and view.action == 'create':
            return True
        
        # Require superadmin for all other operations
        return request.user and request.user.is_authenticated and request.user.is_superuser

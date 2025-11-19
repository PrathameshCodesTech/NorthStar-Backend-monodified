"""
Tenant Middleware - Extract and Set Tenant Context
Supports multiple tenant identification methods
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from core.database_router import set_current_tenant, clear_current_tenant
import logging
import re

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """
    Multi-Tenant Context Middleware
    
    Tenant Identification Priority:
    1. HTTP Header: X-Tenant-Slug
    2. Subdomain: acmecorp.compliance.com → acmecorp
    3. URL Path: /t/acmecorp/dashboard → acmecorp
    
    Sets tenant context for database router to use
    Validates tenant exists and is active
    """
    
    # Paths that don't require tenant context
    # Paths that don't require tenant context
    EXEMPT_PATHS = [
        '/admin/',             # Main admin (but NOT /admin/tenant/)
        '/api/v2/admin/',      # SuperAdmin tenant management
        '/api/v2/auth/',       # Authentication endpoints
        '/api/auth/',          # JWT token endpoints
        '/api/v1/templates/',  # Template management (SuperAdmin only)
        '/api/docs/',
        '/api/redoc/',
        '/static/',
        '/media/',
        '/health/',
    ]
    
    def process_request(self, request):
        """Extract tenant from request and set context"""
        
        # Special handling for tenant admin URLs
        if request.path.startswith('/admin/tenant/') and '/admin/' in request.path:
            # Extract tenant slug from URL: /admin/tenant/{slug}/admin/
            import re
            match = re.match(r'^/admin/tenant/([a-z0-9-]+)/admin/', request.path)
            if match:
                tenant_slug = match.group(1)
                logger.info(f"Tenant admin access: {tenant_slug}")
                
                # Set tenant context
                result = self._set_and_validate_tenant(request, tenant_slug, 'tenant_admin_url')
                if result:
                    return result
                
                # Continue to let admin handle the request
                return None
        
        # Check if path is exempt from tenant requirement
        if self._is_exempt_path(request.path):
            logger.debug(f"Exempt path: {request.path}")
            return None
        
        tenant_slug = None
        identification_method = None
        
        # Method 1: Check HTTP Header (best for API calls)
        tenant_slug = request.META.get('HTTP_X_TENANT_SLUG')
        if tenant_slug:
            identification_method = 'header'
            logger.debug(f"Tenant from header: {tenant_slug}")
        
        # Method 2: Check Subdomain (best for web UI)
        if not tenant_slug:
            tenant_slug = self._extract_from_subdomain(request)
            if tenant_slug:
                identification_method = 'subdomain'
                logger.debug(f"Tenant from subdomain: {tenant_slug}")
        
        # Method 3: Check URL Path (fallback)
        if not tenant_slug:
            tenant_slug = self._extract_from_path(request.path)
            if tenant_slug:
                identification_method = 'path'
                logger.debug(f"Tenant from path: {tenant_slug}")
        
        # If no tenant found and path requires tenant
        if not tenant_slug:
            if self._requires_tenant(request.path):
                logger.warning(f"No tenant context for path: {request.path}")
                return JsonResponse({
                    'error': 'Tenant identification required',
                    'detail': 'Please provide tenant via header (X-Tenant-Slug), subdomain, or URL path'
                }, status=400)
            return None
        
        # Validate and set tenant context
        return self._set_and_validate_tenant(request, tenant_slug, identification_method)
    
    def process_response(self, request, response):
        """Clear tenant context after request processing"""
        clear_current_tenant()
        return response
    
    def process_exception(self, request, exception):
        """Clear tenant context on exception"""
        clear_current_tenant()
        return None
    
    def _is_exempt_path(self, path):
        """Check if path is exempt from tenant requirement"""
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return True
        return False
    
    def _requires_tenant(self, path):
        """Check if path requires tenant context"""
        # API paths that require tenant context
        tenant_required_patterns = [
            r'^/api/v1/company/',     # ✅ Company compliance APIs (tenant-specific)
            r'^/api/v2/tenants/',     # Tenant-specific user management
            r'^/api/tenant/',         # Any other tenant-specific endpoints
            r'^/dashboard/',          # Dashboard UI
            r'^/compliance/',         # Compliance UI
        ]
        
        for pattern in tenant_required_patterns:
            if re.match(pattern, path):
                return True
        
        return False
    
    def _extract_from_subdomain(self, request):
        """Extract tenant slug from subdomain"""
        try:
            host = request.get_host().split(':')[0]  # Remove port
            
            # Check if domain has subdomain
            if '.' in host:
                parts = host.split('.')
                
                if len(parts) >= 2:
                    subdomain = parts[0]
                    
                    # Ignore common subdomains
                    if subdomain not in ['www', 'app', 'api', 'admin', 'localhost']:
                        # Validate subdomain format
                        if re.match(r'^[a-z0-9-]{3,50}$', subdomain):
                            return subdomain
        except Exception as e:
            logger.error(f"Error extracting subdomain: {e}")
        
        return None
    
    def _extract_from_path(self, path):
        """Extract tenant slug from URL path"""
        # Pattern: /t/{tenant_slug}/...
        match = re.match(r'^/t/([a-z0-9-]{3,50})/', path)
        if match:
            return match.group(1)
        
        return None
    
    def _set_and_validate_tenant(self, request, tenant_slug, method):
        """Validate tenant and set context"""
        
        # Validate tenant format
        if not re.match(r'^[a-z0-9-]{3,50}$', tenant_slug):
            logger.warning(f"Invalid tenant_slug format: {tenant_slug}")
            return JsonResponse({
                'error': 'Invalid tenant identifier',
                'detail': f'Tenant slug must be 3-50 lowercase alphanumeric characters with hyphens'
            }, status=400)
        
        # Get tenant info from database
        from tenant_management.models import TenantDatabaseInfo
        
        try:
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            tenant_info = {
                'status': tenant.subscription_status,
                'schema_name': tenant.schema_name,
                'database_name': tenant.database_name,
                'company_name': tenant.company_name
            }
            
        except TenantDatabaseInfo.DoesNotExist:
            logger.warning(f"Tenant not found: {tenant_slug}")
            return JsonResponse({
                'error': 'Tenant not found',
                'detail': f'No tenant found with identifier: {tenant_slug}'
            }, status=404)
        
        # Check if tenant is active
        if tenant_info.get('status') not in ['ACTIVE', 'PENDING_PAYMENT']:
            logger.warning(f"Tenant not active: {tenant_slug} - Status: {tenant_info.get('status')}")
            return JsonResponse({
                'error': 'Tenant not available',
                'detail': f'Tenant is currently {tenant_info.get("status")}. Please contact support.',
                'status': tenant_info.get('status')
            }, status=403)
        
        # Set tenant context
        success = set_current_tenant(tenant_slug)
        
        if not success:
            logger.error(f"Failed to set tenant context: {tenant_slug}")
            return JsonResponse({
                'error': 'Failed to set tenant context',
                'detail': 'Internal error setting tenant context'
            }, status=500)
        
        # Attach tenant info to request for easy access
        request.tenant_slug = tenant_slug
        request.tenant_info = tenant_info
        request.tenant_identification_method = method
        
        logger.info(f"Set tenant context: {tenant_slug} (via {method})")
        
        return None


class TenantAuthorizationMiddleware(MiddlewareMixin):
    """
    Verify user has access to the requested tenant
    Must be placed AFTER AuthenticationMiddleware and TenantMiddleware
    """
    
    def process_request(self, request):
        """Check if authenticated user has access to tenant"""
        
        # Skip if no tenant context or not authenticated
        if not hasattr(request, 'tenant_slug') or not request.user.is_authenticated:
            return None
        
        # SuperAdmin can access all tenants
        if request.user.is_superuser:
            logger.debug(f"SuperAdmin access to tenant: {request.tenant_slug}")
            return None
        
        # Check if user is a member of this tenant
        from user_management.models import TenantMembership
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=request.tenant_slug,
                is_active=True
            )
            
            # Check membership status
            if membership.status not in ['ACTIVE', 'PENDING']:
                logger.warning(
                    f"User {request.user.username} has inactive membership "
                    f"for tenant {request.tenant_slug}: {membership.status}"
                )
                return JsonResponse({
                    'error': 'Access denied',
                    'detail': f'Your access to this tenant is {membership.status}. Please contact your administrator.'
                }, status=403)
            
            # Attach membership to request
            request.tenant_membership = membership
            request.user_role = membership.role
            
            logger.debug(
                f"User {request.user.username} authorized for tenant "
                f"{request.tenant_slug} as {membership.role.code}"
            )
            
            return None
            
        except TenantMembership.DoesNotExist:
            logger.warning(
                f"User {request.user.username} not a member of tenant {request.tenant_slug}"
            )
            return JsonResponse({
                'error': 'Access denied',
                'detail': 'You do not have access to this tenant. Please contact your administrator.'
            }, status=403)
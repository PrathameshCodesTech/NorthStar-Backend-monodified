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
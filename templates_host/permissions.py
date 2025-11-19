"""
Custom permissions for template management
"""

from rest_framework.permissions import BasePermission


class IsSuperAdminUser(BasePermission):
    """
    Only Django superusers can manage framework templates
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )


class IsAdminOrReadOnly(BasePermission):
    """
    SuperAdmin can do anything, others can only read
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Read permissions for authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Write permissions only for superusers
        return request.user.is_superuser
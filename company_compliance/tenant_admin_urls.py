"""
URL Configuration for Tenant-Specific Admin
"""

from django.urls import path
from .tenant_admin_views import TenantAdminListView, tenant_admin_redirect

app_name = 'tenant_admin'

urlpatterns = [
    # List of all tenants (for superadmin)
    path('', TenantAdminListView.as_view(), name='tenant_list'),
    
    # Redirect to specific tenant admin
    path('<slug:tenant_slug>/', tenant_admin_redirect, name='tenant_redirect'),
]
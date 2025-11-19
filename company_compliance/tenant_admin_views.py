"""
Views for Tenant Admin Access
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse

from tenant_management.models import TenantDatabaseInfo
from user_management.models import TenantMembership
from .tenant_admin import create_tenant_admin_site


@method_decorator(staff_member_required, name='dispatch')
class TenantAdminListView(ListView):
    """
    List all tenants with links to their admin panels
    """
    model = TenantDatabaseInfo
    template_name = 'admin/tenant_admin_list.html'
    context_object_name = 'tenants'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = TenantDatabaseInfo.objects.filter(
            is_active=True,
            provisioning_status='ACTIVE'
        ).select_related('subscription_plan').order_by('company_name')
        
        # If not superuser, only show tenants user is member of
        if not self.request.user.is_superuser:
            user_tenants = TenantMembership.objects.filter(
                user=self.request.user,
                is_active=True
            ).values_list('tenant_slug', flat=True)
            queryset = queryset.filter(tenant_slug__in=user_tenants)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Tenant Administration'
        context['is_superuser'] = self.request.user.is_superuser
        return context


@staff_member_required
def tenant_admin_redirect(request, tenant_slug):
    """
    Redirect to tenant-specific admin
    Creates admin site dynamically and includes its URLs
    """
    # Verify tenant exists
    tenant = get_object_or_404(
        TenantDatabaseInfo,
        tenant_slug=tenant_slug,
        is_active=True
    )
    
    # Check permissions
    if not request.user.is_superuser:
        # Check if user is member of this tenant
        has_access = TenantMembership.objects.filter(
            user=request.user,
            tenant_slug=tenant_slug,
            status='ACTIVE',
            is_active=True
        ).exists()
        
        if not has_access:
            messages.error(request, f'You do not have access to {tenant.company_name} admin.')
            return redirect('admin:index')
    
    # Redirect to the dynamically created tenant admin
    return redirect(f'/admin/tenant/{tenant_slug}/admin/')
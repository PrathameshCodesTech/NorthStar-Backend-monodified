"""
Tenant Management API Views - MONOLITH VERSION
Handles tenant provisioning, subscription management, and framework distribution
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q

from .models import (
    SubscriptionPlan, TenantDatabaseInfo, FrameworkSubscription,
    TenantUsageLog, TenantBillingHistory
)
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionPlanListSerializer,
    TenantCreateSerializer, TenantDetailSerializer, TenantListSerializer,
    TenantUpdateSerializer, FrameworkSubscriptionSerializer,
    FrameworkSubscribeSerializer, TenantUsageLogSerializer,
    TenantBillingHistorySerializer
)
from .permissions import IsSuperAdmin, IsSuperAdminOrReadOnly
from .tenant_utils import (
    provision_tenant, add_tenant_database_to_django,
    invalidate_tenant_cache
)


# ============================================================================
# SUBSCRIPTION PLAN VIEWS
# ============================================================================

class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Subscription plan management
    
    list: Get all subscription plans
    retrieve: Get specific plan details
    create: Create new plan (superadmin only)
    update: Update plan (superadmin only)
    """
    
    queryset = SubscriptionPlan.objects.all()
    permission_classes = [IsSuperAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['code', 'is_active', 'default_isolation_mode']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['sort_order', 'monthly_price', 'created_at']
    ordering = ['sort_order']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SubscriptionPlanListSerializer
        return SubscriptionPlanSerializer


# ============================================================================
# TENANT MANAGEMENT VIEWS
# ============================================================================

class TenantViewSet(viewsets.ModelViewSet):
    """
    Tenant management (SuperAdmin only)
    
    list: Get all tenants
    retrieve: Get tenant details
    create: Provision new tenant
    update: Update tenant info
    partial_update: Patch tenant info
    destroy: Soft delete tenant
    
    Custom actions:
    - subscribe: Subscribe tenant to framework
    - suspend: Suspend tenant
    - activate: Activate tenant
    - usage: Get usage statistics
    """
    
    queryset = TenantDatabaseInfo.objects.all()
    permission_classes = [IsSuperAdmin]
    lookup_field = 'tenant_slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subscription_status', 'provisioning_status', 'isolation_mode', 'is_active']
    search_fields = ['tenant_slug', 'company_name', 'company_email']
    ordering_fields = ['created_at', 'company_name', 'subscription_status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on action"""
        queryset = super().get_queryset()
        
        # By default, show only active tenants
        if self.action == 'list':
            show_inactive = self.request.query_params.get('show_inactive', 'false')
            if show_inactive.lower() != 'true':
                queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TenantListSerializer
        elif self.action in ['update', 'partial_update']:
            return TenantUpdateSerializer
        elif self.action == 'create':
            return TenantCreateSerializer
        return TenantDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create and provision new tenant
        
        POST /api/v2/admin/tenants/
        {
            "tenant_slug": "acmecorp",
            "company_name": "AcmeCorp Inc",
            "company_email": "admin@acmecorp.com",
            "subscription_plan_code": "PROFESSIONAL"
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            tenant = serializer.save()
            
            # Return detailed info
            detail_serializer = TenantDetailSerializer(tenant)
            
            return Response(
                {
                    'success': True,
                    'message': f'Tenant "{tenant.company_name}" created successfully',
                    'tenant': detail_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        """Update tenant information"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        # Invalidate cache
        invalidate_tenant_cache(tenant.tenant_slug)
        
        detail_serializer = TenantDetailSerializer(tenant)
        return Response({
            'success': True,
            'message': 'Tenant updated successfully',
            'tenant': detail_serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete tenant"""
        tenant = self.get_object()
        
        # Soft delete
        tenant.is_active = False
        tenant.subscription_status = 'CANCELLED'
        tenant.save()
        
        # Invalidate cache
        invalidate_tenant_cache(tenant.tenant_slug)
        
        return Response({
            'success': True,
            'message': f'Tenant "{tenant.company_name}" has been deactivated',
            'tenant_slug': tenant.tenant_slug,
            'note': 'Tenant marked as inactive. Database/schema still exists.'
        })
    
    #!
    
    # In tenant_management/views.py, update the subscribe action:

    @action(detail=True, methods=['post'])
    def subscribe(self, request, tenant_slug=None):
        """
        Subscribe tenant to framework
        
        POST /api/v2/admin/tenants/{slug}/subscribe/
        {
            "framework_id": "uuid...",
            "customization_level": "CONTROL_LEVEL"
        }
        """
        tenant = self.get_object()
        
        serializer = FrameworkSubscribeSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            # Import here to avoid circular imports
            from templates_host.distribution_utils import copy_framework_to_tenant
            
            # Distribute framework to tenant
            result = copy_framework_to_tenant(
                tenant=tenant,
                framework_id=str(request.data['framework_id']),
                customization_level=request.data.get('customization_level', 'CONTROL_LEVEL')
            )
            
            if not result['success']:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Distribution failed')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create subscription record
            subscription = serializer.save()
            
            return Response({
                'success': True,
                'message': f'Subscribed to framework "{result["framework_name"]}"',
                'subscription': FrameworkSubscriptionSerializer(subscription).data,
                'distribution': result
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, tenant_slug=None):
        """
        Suspend tenant
        
        POST /api/v2/admin/tenants/{slug}/suspend/
        """
        tenant = self.get_object()
        
        if tenant.subscription_status == 'SUSPENDED':
            return Response({
                'success': False,
                'error': 'Tenant is already suspended'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant.subscription_status = 'SUSPENDED'
        tenant.save()
        
        invalidate_tenant_cache(tenant.tenant_slug)
        
        return Response({
            'success': True,
            'message': f'Tenant "{tenant.company_name}" suspended',
            'tenant_slug': tenant.tenant_slug
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, tenant_slug=None):
        """
        Activate/reactivate tenant
        
        POST /api/v2/admin/tenants/{slug}/activate/
        """
        tenant = self.get_object()
        
        if tenant.subscription_status == 'ACTIVE':
            return Response({
                'success': False,
                'error': 'Tenant is already active'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant.subscription_status = 'ACTIVE'
        tenant.is_active = True
        tenant.save()
        
        invalidate_tenant_cache(tenant.tenant_slug)
        
        return Response({
            'success': True,
            'message': f'Tenant "{tenant.company_name}" activated',
            'tenant_slug': tenant.tenant_slug
        })
    
    @action(detail=True, methods=['get'])
    def usage(self, request, tenant_slug=None):
        """
        Get tenant usage statistics
        
        GET /api/v2/admin/tenants/{slug}/usage/
        """
        tenant = self.get_object()
        
        # Get recent usage logs
        recent_logs = TenantUsageLog.objects.filter(
            tenant=tenant
        ).order_by('-log_date')[:30]
        
        usage_data = TenantUsageLogSerializer(recent_logs, many=True).data
        
        return Response({
            'tenant_slug': tenant.tenant_slug,
            'company_name': tenant.company_name,
            'current_usage': {
                'users': tenant.current_user_count,
                'frameworks': tenant.current_framework_count,
                'controls': tenant.current_control_count,
                'storage_gb': float(tenant.storage_used_gb)
            },
            'plan_limits': {
                'max_users': tenant.subscription_plan.max_users,
                'max_frameworks': tenant.subscription_plan.max_frameworks,
                'max_controls': tenant.subscription_plan.max_controls,
                'storage_gb': tenant.subscription_plan.storage_gb
            },
            'usage_history': usage_data
        })
    
    @action(detail=True, methods=['get'])
    def frameworks(self, request, tenant_slug=None):
        """
        Get tenant's subscribed frameworks
        
        GET /api/v2/admin/tenants/{slug}/frameworks/
        """
        tenant = self.get_object()
        
        subscriptions = FrameworkSubscription.objects.filter(
            tenant=tenant,
            status='ACTIVE'
        )
        
        serializer = FrameworkSubscriptionSerializer(subscriptions, many=True)
        
        return Response({
            'tenant_slug': tenant.tenant_slug,
            'framework_count': subscriptions.count(),
            'frameworks': serializer.data
        })


# ============================================================================
# FRAMEWORK SUBSCRIPTION VIEWS
# ============================================================================

class FrameworkSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Framework subscription management (read-only)
    
    Use TenantViewSet.subscribe() to create subscriptions
    """
    
    queryset = FrameworkSubscription.objects.all()
    serializer_class = FrameworkSubscriptionSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tenant__tenant_slug', 'status', 'customization_level']
    search_fields = ['framework_name', 'tenant__company_name']
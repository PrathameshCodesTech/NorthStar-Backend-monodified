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
    TenantUsageLog, TenantBillingHistory,SuperAdminAuditLog
)
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionPlanListSerializer,
    TenantCreateSerializer, TenantDetailSerializer, TenantListSerializer,
    TenantUpdateSerializer, FrameworkSubscriptionSerializer,
    FrameworkSubscribeSerializer, TenantUsageLogSerializer,
    TenantBillingHistorySerializer, SuperAdminAuditLogSerializer
)
from .permissions import IsSuperAdmin, IsSuperAdminOrReadOnly,AllowUnauthenticatedRead,AllowTenantCreation
from .tenant_utils import (
    create_tenant_record, activate_tenant_with_framework,
    delete_pending_tenant, add_tenant_database_to_django,
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
    permission_classes = [AllowUnauthenticatedRead]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['code', 'is_active']
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
    permission_classes = [AllowTenantCreation]
    lookup_field = 'tenant_slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subscription_status', 'provisioning_status', 'is_active']
    search_fields = ['tenant_slug', 'company_name', 'company_email']
    ordering_fields = ['created_at', 'company_name', 'subscription_status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on action"""
        queryset = super().get_queryset()
        
        # By default, show only active/pending tenants (hide deleted)
        if self.action == 'list':
            show_deleted = self.request.query_params.get('show_deleted', 'false')
            if show_deleted.lower() != 'true':
                queryset = queryset.exclude(subscription_status='DELETED')
        
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
        Create tenant record (minimal) - awaiting payment
        
        POST /api/v2/admin/tenants/
        {
            "company_name": "AcmeCorp Inc",
            "company_email": "admin@acmecorp.com",
            "subscription_plan_code": "PROFESSIONAL"
            // tenant_slug is optional - auto-generated from company_name
        }
        
        Response:
        {
            "success": true,
            "tenant_slug": "acmecorp",
            "status": "PENDING_PAYMENT",
            "payment_required": true,
            "amount": 599.00,
            "message": "Tenant record created. Please complete payment to activate.",
            "next_step": "POST /api/v2/admin/tenants/{slug}/activate/"
        }
        """
        from .tenant_utils import create_tenant_record
        from .validators import validate_and_normalize_slug
        from .models import TenantDatabaseInfo
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Get validated data
            company_name = serializer.validated_data['company_name']
            company_email = serializer.validated_data['company_email']
            subscription_plan_code = serializer.validated_data.get('subscription_plan_code', 'BASIC')
            
            # Auto-generate tenant_slug if not provided
            tenant_slug = serializer.validated_data.get('tenant_slug')
            if not tenant_slug:
                # Generate unique slug from company name
                base_slug = validate_and_normalize_slug(company_name)
                tenant_slug = base_slug
                counter = 2
                
                # Keep incrementing until we find unique slug
                while TenantDatabaseInfo.objects.filter(tenant_slug=tenant_slug).exists():
                    tenant_slug = f"{base_slug}-{counter}"
                    counter += 1
            
            # Create tenant record only (no schema yet)
            # ✅ NEW: Extract requested frameworks
            requested_frameworks = serializer.validated_data.get('requested_frameworks', [])
            
            # Create tenant record only (no schema yet)
            result = create_tenant_record(
                tenant_slug=tenant_slug,
                company_name=company_name,
                company_email=company_email,
                subscription_plan_code=subscription_plan_code,
                requested_frameworks=requested_frameworks  # ✅ Pass frameworks
            )
            
            tenant = result['tenant_info']
            
            tenant = result['tenant_info']
            
            # Return payment info
            return Response(
                {
                    'success': True,
                    'tenant_slug': tenant.tenant_slug,
                    'company_name': tenant.company_name,
                    'status': tenant.subscription_status,
                    'payment_required': result['payment_required'],
                    'amount': float(result['amount']),
                    'currency': 'USD',
                    'plan': tenant.subscription_plan.name,
                    'message': result['message'],
                    'next_step': f'POST /api/v2/admin/tenants/{tenant.tenant_slug}/activate/'
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
    
    @action(detail=True, methods=['post'])
    def activate(self, request, tenant_slug=None):
        """
        Activate tenant after payment confirmation
        Creates schema, runs migrations, subscribes to framework
        
        POST /api/v2/admin/tenants/{slug}/activate/
        {
            "framework_id": "uuid-of-framework",
            "customization_level": "CONTROL_LEVEL",  # Optional
            "payment_id": "pay_xxxxx"  # Optional reference
        }
        
        This should be called AFTER payment is confirmed
        """
        tenant = self.get_object()
        
        # Validate tenant status
        if tenant.subscription_status != 'PENDING_PAYMENT':
            return Response({
                'success': False,
                'error': f'Tenant cannot be activated. Current status: {tenant.subscription_status}',
                'current_status': tenant.subscription_status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate activation data
        from .serializers import TenantActivationSerializer
        
        serializer = TenantActivationSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            # Activate tenant (creates schema + subscribes to framework)
            activated_tenant = serializer.save()
            
            # Return full tenant details
            detail_serializer = TenantDetailSerializer(activated_tenant)
            
            return Response({
                'success': True,
                'message': f'Tenant "{activated_tenant.company_name}" activated successfully',
                'tenant': detail_serializer.data,
                'status': activated_tenant.subscription_status,
                'framework_subscribed': True
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['delete'])
    def delete_pending(self, request, tenant_slug=None):
        """
        Delete pending tenant (payment failed or cancelled)
        Only works if status is PENDING_PAYMENT
        
        DELETE /api/v2/admin/tenants/{slug}/delete_pending/
        """
        from .tenant_utils import delete_pending_tenant
        
        try:
            result = delete_pending_tenant(tenant_slug)
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': result['message'],
                    'tenant_slug': tenant_slug
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result['message']
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


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
        Subscribe tenant to ADDITIONAL framework
        (For already-active tenants who want to add more frameworks)
        
        POST /api/v2/admin/tenants/{slug}/subscribe/
        {
            "framework_id": "uuid...",
            "customization_level": "CONTROL_LEVEL"  # Optional - will be enforced by plan
        }
        
        Note: For NEW tenants, use POST /activate/ instead
        """
        tenant = self.get_object()
        
        # Check if tenant is already active
        if tenant.subscription_status != 'ACTIVE':
            return Response({
                'success': False,
                'error': f'Tenant must be ACTIVE to subscribe to additional frameworks. Current status: {tenant.subscription_status}',
                'hint': 'Use POST /activate/ to activate a pending tenant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        
        serializer = FrameworkSubscribeSerializer(
            data=request.data,
            context={'tenant': tenant}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            # Import here to avoid circular imports
            from templates_host.distribution_utils import copy_framework_to_tenant
            
            # ============ ENFORCE CUSTOMIZATION LEVEL BASED ON PLAN ============
            plan = tenant.subscription_plan
            
            # Determine customization level based on subscription plan
            if plan.code == 'BASIC':
                # BASIC: Force VIEW_ONLY (no framework copy)
                customization_level = 'VIEW_ONLY'
                
            elif plan.code == 'PROFESSIONAL':
                # PROFESSIONAL: Force CONTROL_LEVEL (can customize controls)
                customization_level = 'CONTROL_LEVEL'
                
            elif plan.code == 'ENTERPRISE':
                # ENTERPRISE: Allow user's choice OR default to FULL
                customization_level = request.data.get('customization_level', 'FULL')
                
                # Validate user's choice is allowed
                if customization_level not in ['VIEW_ONLY', 'CONTROL_LEVEL', 'FULL']:
                    return Response({
                        'success': False,
                        'error': f'Invalid customization_level: {customization_level}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Unknown plan - use plan's default
                customization_level = plan.default_customization_level
            
            # Log the enforcement
            from django.utils import timezone
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[PLAN ENFORCEMENT] Tenant: {tenant.tenant_slug}, "
                f"Plan: {plan.code}, "
                f"Requested: {request.data.get('customization_level', 'none')}, "
                f"Enforced: {customization_level}"
            )
            # ====================================================================
            
            # Distribute framework to tenant
            result = copy_framework_to_tenant(
                tenant=tenant,
                framework_id=str(request.data['framework_id']),
                customization_level=customization_level  # Use enforced level
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
    def reactivate(self, request, tenant_slug=None):
        """
        Reactivate suspended tenant
        
        POST /api/v2/admin/tenants/{slug}/reactivate/
        """
        tenant = self.get_object()
        
        if tenant.subscription_status != 'SUSPENDED':
            return Response({
                'success': False,
                'error': f'Can only reactivate suspended tenants. Current status: {tenant.subscription_status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant.subscription_status = 'ACTIVE'
        tenant.save()
        
        invalidate_tenant_cache(tenant.tenant_slug)
        
        return Response({
            'success': True,
            'message': f'Tenant "{tenant.company_name}" reactivated successfully',
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


# ============================================================================
# BILLING HISTORY VIEWS
# ============================================================================

class TenantBillingHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Billing history management (read-only)
    
    list: Get all billing records
    retrieve: Get specific invoice details
    """
    
    queryset = TenantBillingHistory.objects.all()
    serializer_class = TenantBillingHistorySerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tenant__tenant_slug', 'payment_status', 'billing_period_start']
    search_fields = ['invoice_number', 'tenant__company_name']
    ordering_fields = ['billing_period_start', 'payment_date', 'total_amount']
    ordering = ['-billing_period_start']
    
    @action(detail=False, methods=['get'])
    def pending_payments(self, request):
        """
        Get all pending payments
        
        GET /api/v2/admin/billing-history/pending_payments/
        """
        pending = self.queryset.filter(payment_status='PENDING')
        serializer = self.get_serializer(pending, many=True)
        
        return Response({
            'count': pending.count(),
            'total_amount': sum([float(b.total_amount) for b in pending]),
            'invoices': serializer.data
        })


# ============================================================================
# USAGE LOG VIEWS
# ============================================================================

class TenantUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Usage logs (read-only)
    
    list: Get all usage logs
    retrieve: Get specific log
    """
    
    queryset = TenantUsageLog.objects.all()
    serializer_class = TenantUsageLogSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tenant__tenant_slug', 'log_date']
    ordering_fields = ['log_date']
    ordering = ['-log_date']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get usage summary across all tenants
        
        GET /api/v2/admin/usage-logs/summary/
        """
        from django.db.models import Sum, Avg
        
        summary = self.queryset.aggregate(
            total_users=Sum('user_count'),
            total_frameworks=Sum('framework_count'),
            total_controls=Sum('control_count'),
            total_storage_gb=Sum('storage_used_gb'),
            avg_api_calls=Avg('api_calls_count')
        )
        
        return Response(summary)


# ============================================================================
# AUDIT LOG VIEWS
# ============================================================================

class SuperAdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    SuperAdmin audit logs (read-only)
    
    list: Get all audit logs
    retrieve: Get specific log entry
    """
    
    queryset = SuperAdminAuditLog.objects.all()
    serializer_class = SuperAdminAuditLogSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['admin_user_id', 'action', 'tenant_slug']
    search_fields = ['admin_username', 'tenant_slug', 'reason']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
    
    @action(detail=False, methods=['get'])
    def by_admin(self, request):
        """
        Get logs grouped by admin user
        
        GET /api/v2/admin/audit-logs/by_admin/
        """
        from django.db.models import Count
        
        admin_summary = self.queryset.values(
            'admin_user_id', 'admin_username'
        ).annotate(
            action_count=Count('id')
        ).order_by('-action_count')
        
        return Response(list(admin_summary))
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        Get recent audit logs (last 100)
        
        GET /api/v2/admin/audit-logs/recent/
        """
        recent_logs = self.queryset.order_by('-timestamp')[:100]
        serializer = self.get_serializer(recent_logs, many=True)
        
        return Response(serializer.data)
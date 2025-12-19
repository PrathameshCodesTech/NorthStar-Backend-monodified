"""
URL Configuration for Tenant Management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'tenant_management'

router = DefaultRouter()
router.register(r'subscription-plans', views.SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'tenants', views.TenantViewSet, basename='tenant')
router.register(r'framework-subscriptions', views.FrameworkSubscriptionViewSet, basename='framework-subscription')
router.register(r'billing-history', views.TenantBillingHistoryViewSet, basename='billing-history')
router.register(r'usage-logs', views.TenantUsageLogViewSet, basename='usage-log')
router.register(r'audit-logs', views.SuperAdminAuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]
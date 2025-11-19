"""
URL Configuration for User Management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'user_management'

router = DefaultRouter()
router.register(r'roles', views.RoleViewSet, basename='role')

urlpatterns = [
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    path('auth/login/', views.UserLoginView.as_view(), name='login'),
    
    # ========================================================================
    # CURRENT USER
    # ========================================================================
    path('me/', views.CurrentUserView.as_view(), name='current-user'),
    path('me/memberships/', views.CurrentUserMembershipsView.as_view(), name='my-memberships'),
    
    # ========================================================================
    # TENANT-SPECIFIC ENDPOINTS
    # ========================================================================
    path(
        'tenants/<str:tenant_slug>/members/',
        views.TenantMembershipViewSet.as_view({'get': 'list'}),
        name='tenant-members'
    ),
    path(
        'tenants/<str:tenant_slug>/members/<uuid:pk>/',
        views.TenantMembershipViewSet.as_view({'get': 'retrieve'}),
        name='tenant-member-detail'
    ),
    path(
        'tenants/<str:tenant_slug>/invitations/',
        views.TenantInvitationViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='tenant-invitations'
    ),
    path(
        'tenants/<str:tenant_slug>/invitations/<uuid:pk>/',
        views.TenantInvitationViewSet.as_view({'get': 'retrieve'}),
        name='tenant-invitation-detail'
    ),
    
    # ========================================================================
    # INVITATIONS
    # ========================================================================
    path('invitations/accept/', views.AcceptInvitationView.as_view(), name='accept-invitation'),
    
    # ========================================================================
    # ROUTER (Roles, etc.)
    # ========================================================================
    path('', include(router.urls)),
]
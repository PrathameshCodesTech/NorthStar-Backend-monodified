"""
User Management API Views
Handles authentication, user registration, profile, and tenant membership
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import Role, TenantMembership, TenantInvitation
from .serializers import (
    UserRegistrationSerializer, UserSerializer, UserProfileSerializer,
    RoleSerializer, RoleListSerializer,
    TenantMembershipSerializer, TenantMembershipListSerializer,
    TenantInvitationCreateSerializer, TenantInvitationSerializer,
    AcceptInvitationSerializer
)
from tenant_management.models import TenantDatabaseInfo


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

class UserRegistrationView(generics.CreateAPIView):
    """
    User registration
    
    POST /api/v2/auth/register/
    {
        "username": "john",
        "email": "john@example.com",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
        "first_name": "John",
        "last_name": "Doe",
        "tenant_slug": "acmecorp",  // Optional
        "role_code": "EMPLOYEE"      // Optional
    }
    """
    
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        }, status=status.HTTP_201_CREATED)


class UserLoginView(generics.GenericAPIView):
    """
    User login
    
    POST /api/v2/auth/login/
    {
        "username": "john",
        "password": "SecurePass123!"
    }
    
    Or use email:
    {
        "email": "john@example.com",
        "password": "SecurePass123!"
    }
    """
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not password:
            return Response({
                'error': 'Password is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to get user by email if provided
        if email and not username:
            try:
                user_obj = User.objects.get(email=email.lower())
                username = user_obj.username
            except User.DoesNotExist:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not username:
            return Response({
                'error': 'Username or email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Authenticate
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({
                'error': 'Account is disabled'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Get user profile with memberships
        profile_data = UserProfileSerializer(user).data
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': profile_data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        })


# ============================================================================
# USER PROFILE VIEWS
# ============================================================================

class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Get or update current user profile
    
    GET /api/v2/users/me/
    PATCH /api/v2/users/me/
    {
        "first_name": "John",
        "last_name": "Doe",
        "email": "newemail@example.com"
    }
    """
    
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class CurrentUserMembershipsView(generics.ListAPIView):
    """
    Get current user's tenant memberships
    
    GET /api/v2/users/me/memberships/
    """
    
    serializer_class = TenantMembershipListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return TenantMembership.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('role')


# ============================================================================
# ROLE VIEWS
# ============================================================================

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List available roles
    
    GET /api/v2/roles/
    GET /api/v2/roles/{id}/
    """
    
    queryset = Role.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_system_role']
    search_fields = ['name', 'code', 'description']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RoleListSerializer
        return RoleSerializer


# ============================================================================
# TENANT MEMBERSHIP VIEWS
# ============================================================================

class TenantMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View tenant members (tenant-specific)
    
    GET /api/v2/tenants/{tenant_slug}/members/
    GET /api/v2/tenants/{tenant_slug}/members/{id}/
    """
    
    serializer_class = TenantMembershipSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'role__code']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    
    def get_queryset(self):
        tenant_slug = self.kwargs.get('tenant_slug')
        
        # Verify user has access to this tenant
        if not self.request.user.is_superuser:
            membership = TenantMembership.objects.filter(
                user=self.request.user,
                tenant_slug=tenant_slug,
                is_active=True
            ).first()
            
            if not membership:
                return TenantMembership.objects.none()
        
        return TenantMembership.objects.filter(
            tenant_slug=tenant_slug,
            is_active=True
        ).select_related('user', 'role')


# ============================================================================
# INVITATION VIEWS
# ============================================================================

class TenantInvitationViewSet(viewsets.ModelViewSet):
    """
    Manage tenant invitations
    
    POST /api/v2/tenants/{tenant_slug}/invitations/
    GET /api/v2/tenants/{tenant_slug}/invitations/
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['email']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TenantInvitationCreateSerializer
        return TenantInvitationSerializer
    
    def get_queryset(self):
        tenant_slug = self.kwargs.get('tenant_slug')
        
        # Verify user has permission to manage this tenant
        if not self.request.user.is_superuser:
            membership = TenantMembership.objects.filter(
                user=self.request.user,
                tenant_slug=tenant_slug,
                is_active=True
            ).first()
            
            if not membership or not membership.can_manage_users:
                return TenantInvitation.objects.none()
        
        return TenantInvitation.objects.filter(
            tenant_slug=tenant_slug
        ).select_related('role', 'invited_by')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant_slug'] = self.kwargs.get('tenant_slug')
        return context
    
    def create(self, request, *args, **kwargs):
        """Send invitation"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        
        return Response({
            'success': True,
            'message': f'Invitation sent to {invitation.email}',
            'invitation': TenantInvitationSerializer(invitation).data
        }, status=status.HTTP_201_CREATED)


class AcceptInvitationView(generics.CreateAPIView):
    """
    Accept invitation (for existing users)
    
    POST /api/v2/invitations/accept/
    {
        "token": "uuid..."
    }
    """
    
    serializer_class = AcceptInvitationSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Invitation accepted successfully',
            'membership': TenantMembershipSerializer(membership).data
        }, status=status.HTTP_201_CREATED)
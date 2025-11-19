"""
User Management Serializers
Handles user registration, authentication, profile, and tenant membership
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import Role, RolePermission, TenantMembership, TenantInvitation
from tenant_management.models import TenantDatabaseInfo


# ============================================================================
# USER SERIALIZERS
# ============================================================================

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    User registration with optional tenant membership
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    tenant_slug = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Tenant to join (optional during registration)"
    )
    role_code = serializers.CharField(
        required=False,
        default='EMPLOYEE',
        help_text="Role code (default: EMPLOYEE)"
    )
    invitation_token = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Invitation token if accepting invite"
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'tenant_slug', 'role_code',
            'invitation_token'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': False},
            'last_name': {'required': False}
        }
    
    def validate_email(self, value):
        """Validate email is unique"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value.lower()
    
    def validate_username(self, value):
        """Validate username is unique and valid"""
        if User.objects.filter(username=value.lower()).exists():
            raise serializers.ValidationError("Username already taken")
        
        # Basic username validation
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters")
        
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )
        
        return value.lower()
    
    def validate(self, data):
        """Validate passwords match and tenant/role if provided"""
        
        # Check passwords match
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match'
            })
        
        # If tenant_slug provided, validate it exists
        tenant_slug = data.get('tenant_slug')
        if tenant_slug:
            try:
                tenant = TenantDatabaseInfo.objects.get(
                    tenant_slug=tenant_slug,
                    is_active=True
                )
                data['tenant'] = tenant
            except TenantDatabaseInfo.DoesNotExist:
                raise serializers.ValidationError({
                    'tenant_slug': f'Tenant "{tenant_slug}" not found'
                })
            
            # Validate role exists
            role_code = data.get('role_code', 'EMPLOYEE')
            try:
                role = Role.objects.get(code=role_code, is_active=True)
                data['role'] = role
            except Role.DoesNotExist:
                raise serializers.ValidationError({
                    'role_code': f'Role "{role_code}" not found'
                })
        
        # If invitation token provided, validate it
        invitation_token = data.get('invitation_token')
        if invitation_token:
            try:
                invitation = TenantInvitation.objects.get(
                    token=invitation_token,
                    status='PENDING'
                )
                
                # Check if expired
                if invitation.is_expired:
                    raise serializers.ValidationError({
                        'invitation_token': 'Invitation has expired'
                    })
                
                # Check email matches
                if invitation.email.lower() != data['email'].lower():
                    raise serializers.ValidationError({
                        'email': 'Email does not match invitation'
                    })
                
                data['invitation'] = invitation
                
            except TenantInvitation.DoesNotExist:
                raise serializers.ValidationError({
                    'invitation_token': 'Invalid invitation token'
                })
        
        return data
    
    def create(self, validated_data):
        """Create user and optional tenant membership"""
        
        # Remove non-user fields
        validated_data.pop('password_confirm')
        tenant = validated_data.pop('tenant', None)
        role = validated_data.pop('role', None)
        invitation = validated_data.pop('invitation', None)
        validated_data.pop('tenant_slug', None)
        validated_data.pop('role_code', None)
        validated_data.pop('invitation_token', None)
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Create tenant membership if provided
        if tenant and role:
            membership = TenantMembership.objects.create(
                user=user,
                tenant_slug=tenant.tenant_slug,
                role=role,
                status='ACTIVE',
                joined_at=timezone.now()
            )
            
            # Mark invitation as accepted if exists
            if invitation:
                invitation.status = 'ACCEPTED'
                invitation.accepted_by = user
                invitation.accepted_at = timezone.now()
                invitation.save()
        
        return user


class UserSerializer(serializers.ModelSerializer):
    """Basic user information"""
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'is_active', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_full_name(self, obj):
        """Get full name or username"""
        if obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile with memberships"""
    
    full_name = serializers.SerializerMethodField()
    tenant_memberships = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login', 'tenant_memberships'
        ]
        read_only_fields = [
            'id', 'username', 'is_staff', 'is_superuser',
            'date_joined', 'last_login'
        ]
    
    def get_full_name(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username
    
    def get_tenant_memberships(self, obj):
        """Get user's tenant memberships"""
        memberships = TenantMembership.objects.filter(
            user=obj,
            is_active=True
        ).select_related('role')
        
        return TenantMembershipListSerializer(memberships, many=True).data


# ============================================================================
# ROLE SERIALIZERS
# ============================================================================

class RoleSerializer(serializers.ModelSerializer):
    """Role details with permissions"""
    
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'code', 'name', 'description',
            'is_system_role', 'is_active', 'permissions'
        ]
    
    def get_permissions(self, obj):
        """Get role permissions"""
        permissions = obj.permissions.all()
        return [
            {
                'code': p.permission_code,
                'name': p.permission_name,
                'description': p.description
            }
            for p in permissions
        ]


class RoleListSerializer(serializers.ModelSerializer):
    """Simplified role listing"""
    
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = ['id', 'code', 'name', 'description', 'permission_count']
    
    def get_permission_count(self, obj):
        return obj.permissions.count()


# ============================================================================
# TENANT MEMBERSHIP SERIALIZERS
# ============================================================================

class TenantMembershipSerializer(serializers.ModelSerializer):
    """Detailed tenant membership"""
    
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    tenant_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantMembership
        fields = [
            'id', 'user', 'tenant_slug', 'tenant_name', 'role',
            'status', 'joined_at', 'last_activity', 'is_active'
        ]
    
    def get_tenant_name(self, obj):
        """Get tenant company name"""
        try:
            tenant = TenantDatabaseInfo.objects.get(tenant_slug=obj.tenant_slug)
            return tenant.company_name
        except TenantDatabaseInfo.DoesNotExist:
            return obj.tenant_slug


class TenantMembershipListSerializer(serializers.ModelSerializer):
    """Simplified membership listing"""
    
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    tenant_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantMembership
        fields = [
            'id', 'tenant_slug', 'tenant_name', 'role_name',
            'role_code', 'status', 'joined_at', 'is_admin'
        ]
    
    def get_tenant_name(self, obj):
        try:
            tenant = TenantDatabaseInfo.objects.get(tenant_slug=obj.tenant_slug)
            return tenant.company_name
        except TenantDatabaseInfo.DoesNotExist:
            return obj.tenant_slug


# ============================================================================
# INVITATION SERIALIZERS
# ============================================================================

class TenantInvitationCreateSerializer(serializers.Serializer):
    """Create invitation to join tenant"""
    
    email = serializers.EmailField(required=True)
    role_code = serializers.CharField(required=True)
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional welcome message"
    )
    
    def validate_email(self, value):
        """Validate email format"""
        return value.lower()
    
    def validate_role_code(self, value):
        """Validate role exists"""
        try:
            Role.objects.get(code=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError(f'Role "{value}" not found')
        return value
    
    def validate(self, data):
        """Validate invitation doesn't already exist"""
        tenant_slug = self.context.get('tenant_slug')
        email = data['email']
        
        # Check if user already exists and is member
        try:
            user = User.objects.get(email=email)
            if TenantMembership.objects.filter(
                user=user,
                tenant_slug=tenant_slug,
                is_active=True
            ).exists():
                raise serializers.ValidationError({
                    'email': 'User is already a member of this tenant'
                })
        except User.DoesNotExist:
            pass  # User doesn't exist, invitation is valid
        
        # Check if pending invitation already exists
        if TenantInvitation.objects.filter(
            email=email,
            tenant_slug=tenant_slug,
            status='PENDING'
        ).exists():
            raise serializers.ValidationError({
                'email': 'Pending invitation already exists for this email'
            })
        
        return data
    
    def create(self, validated_data):
        """Create invitation"""
        tenant_slug = self.context['tenant_slug']
        invited_by = self.context['request'].user
        
        role = Role.objects.get(code=validated_data['role_code'])
        
        # Create invitation
        invitation = TenantInvitation.objects.create(
            email=validated_data['email'],
            tenant_slug=tenant_slug,
            role=role,
            invited_by=invited_by,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7),  # 7 days expiry
            token=uuid.uuid4(),
            status='PENDING'
        )
        
        # TODO: Send invitation email
        # send_invitation_email(invitation, validated_data.get('message'))
        
        return invitation


class TenantInvitationSerializer(serializers.ModelSerializer):
    """Invitation details"""
    
    invited_by_name = serializers.CharField(
        source='invited_by.username',
        read_only=True
    )
    role_name = serializers.CharField(source='role.name', read_only=True)
    tenant_name = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TenantInvitation
        fields = [
            'id', 'email', 'tenant_slug', 'tenant_name', 'role_name',
            'token', 'status', 'invited_by_name', 'created_at',
            'expires_at', 'is_expired', 'accepted_at'
        ]
        read_only_fields = ['token']
    
    def get_tenant_name(self, obj):
        try:
            tenant = TenantDatabaseInfo.objects.get(tenant_slug=obj.tenant_slug)
            return tenant.company_name
        except TenantDatabaseInfo.DoesNotExist:
            return obj.tenant_slug


class AcceptInvitationSerializer(serializers.Serializer):
    """Accept invitation (for existing users)"""
    
    token = serializers.UUIDField(required=True)
    
    def validate_token(self, value):
        """Validate invitation exists and is valid"""
        try:
            invitation = TenantInvitation.objects.get(
                token=value,
                status='PENDING'
            )
            
            if invitation.is_expired:
                raise serializers.ValidationError('Invitation has expired')
            
            return value
            
        except TenantInvitation.DoesNotExist:
            raise serializers.ValidationError('Invalid or already used invitation token')
    
    def create(self, validated_data):
        """Accept invitation and create membership"""
        user = self.context['request'].user
        token = validated_data['token']
        
        invitation = TenantInvitation.objects.get(token=token, status='PENDING')
        
        # Create membership
        membership = TenantMembership.objects.create(
            user=user,
            tenant_slug=invitation.tenant_slug,
            role=invitation.role,
            status='ACTIVE',
            invited_by=invitation.invited_by,
            invited_at=invitation.created_at,
            joined_at=timezone.now()
        )
        
        # Mark invitation as accepted
        invitation.status = 'ACCEPTED'
        invitation.accepted_by = user
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        return membership
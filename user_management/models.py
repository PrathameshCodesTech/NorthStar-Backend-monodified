"""
User Management Models
Handles users, roles, and tenant memberships in main database
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from .permission_registry import SUPPORTED_PERMISSIONS


class Role(models.Model):
    """
    Role definitions (TENANT_ADMIN, EMPLOYEE, MANAGER, AUDITOR)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Role code like 'TENANT_ADMIN', 'EMPLOYEE'"
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name like 'Tenant Administrator'"
    )
    description = models.TextField(blank=True)
    
    # NEW: Prevent deletion of critical roles
    is_system_role = models.BooleanField(
        default=False,
        help_text="System roles cannot be deleted"
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_management_role'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class RolePermission(models.Model):
    """
    Granular permissions for roles
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        related_name='permissions',
        on_delete=models.CASCADE
    )
    # DROPDOWN!
    permission_code = models.CharField(
        max_length=100,
        choices=SUPPORTED_PERMISSIONS,  # ← CHANGE HERE
        help_text="Permission code like 'assign_controls', 'manage_users'"
    )
    permission_name = models.CharField(
        max_length=200,
        help_text="Display name like 'Can assign controls to users'"
    )
    description = models.TextField(
        blank=True,
        help_text="What this permission allows"
    )
    class Meta:
        db_table = 'user_management_rolepermission'
        unique_together = ['role', 'permission_code']
        ordering = ['role', 'permission_code']
    def __str__(self):
        return f"{self.role.code} → {self.permission_code}"


class TenantMembership(models.Model):
    """Links users to tenants with specific roles"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Invitation'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('INACTIVE', 'Inactive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tenant_memberships'
    )
    tenant_slug = models.CharField(
        max_length=50,
        help_text="References tenant from tenant_management"
    )
    role = models.ForeignKey(
        Role,
        related_name='memberships',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    
    # Metadata
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_memberships'
    )
    invited_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When invitation was sent"
    )
    joined_at = models.DateTimeField(
        default=timezone.now,
        help_text="When user accepted invitation"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last time user accessed this tenant"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_management_tenantmembership'
        unique_together = ['user', 'tenant_slug']
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['user', 'tenant_slug']),
            models.Index(fields=['tenant_slug', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} → {self.tenant_slug} ({self.role.code})"
    
    @property
    def is_admin(self):
        """Check if user has admin privileges"""
        return bool(self.role and self.role.code in ['TENANT_ADMIN', 'COMPLIANCE_MANAGER'])
    
    @property
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.has_permission('manage_users')
    
    @property
    def can_assign_controls(self):
        """Check if user can assign controls"""
        return self.has_permission('assign_controls')
    
    def has_permission(self, permission_code: str) -> bool:
        """Check if user has specific permission"""
        if not self.role_id:
            return False
        return self.role.permissions.filter(permission_code=permission_code).exists()
    
    @property
    def allowed_permissions(self):
        """List all allowed permission codes"""
        if not self.role_id:
            return []
        return list(self.role.permissions.values_list('permission_code', flat=True))


class TenantInvitation(models.Model):
    """Pending invitations for users to join tenants"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(help_text="Email address to invite")
    tenant_slug = models.CharField(
        max_length=50,
        help_text="Which tenant to join"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        help_text="Role to assign upon acceptance"
    )
    
    # Invitation token
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique token for invitation link"
    )
    
    # Metadata
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(help_text="When invitation expires")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('ACCEPTED', 'Accepted'),
            ('EXPIRED', 'Expired'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='PENDING'
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_invitations'
    )
    
    class Meta:
        db_table = 'user_management_tenantinvitation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'tenant_slug', 'status']),
            models.Index(fields=['token']),
        ]
    
    def __str__(self):
        return f"Invite {self.email} → {self.tenant_slug} ({self.role.code})"
    
    @property
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at and self.status == 'PENDING'
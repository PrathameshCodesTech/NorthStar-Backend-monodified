"""
Permissions for company compliance operations
Complete RBAC implementation for all 23 permissions
"""

from rest_framework.permissions import BasePermission
from user_management.models import TenantMembership


# ============================================================================
# BASE PERMISSIONS
# ============================================================================

class IsTenantMember(BasePermission):
    """
    User must be an active member of the tenant
    SuperAdmin has access to all tenants
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        return TenantMembership.objects.filter(
            user=request.user,
            tenant_slug=tenant_slug,
            status='ACTIVE',
            is_active=True
        ).exists()


class IsTenantAdmin(BasePermission):
    """
    User must be a tenant admin
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE',
                is_active=True
            )
            return membership.is_admin
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# TENANT_ADMIN PERMISSIONS (8 permissions)
# ============================================================================

class CanManageUsers(BasePermission):
    """
    Permission: manage_users
    Can invite, remove, and manage user roles
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('manage_users')
        except TenantMembership.DoesNotExist:
            return False


class CanManageFrameworks(BasePermission):
    """
    Permission: manage_frameworks
    Can subscribe to and customize frameworks
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('manage_frameworks')
        except TenantMembership.DoesNotExist:
            return False


class CanManageSettings(BasePermission):
    """
    Permission: manage_settings
    Can update company settings and preferences
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('manage_settings')
        except TenantMembership.DoesNotExist:
            return False


class CanManageBilling(BasePermission):
    """
    Permission: manage_billing
    Can view and manage billing information
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('manage_billing')
        except TenantMembership.DoesNotExist:
            return False


class CanViewAuditLogs(BasePermission):
    """
    Permission: view_audit_logs
    Can view system audit logs
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_audit_logs')
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# CONTROL & CAMPAIGN PERMISSIONS
# ============================================================================

class CanAssignControls(BasePermission):
    """
    Permission: assign_controls
    Can assign controls to team members
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('assign_controls')
        except TenantMembership.DoesNotExist:
            return False


class CanCreateCampaigns(BasePermission):
    """
    Permission: create_campaigns
    Can create and manage assessment campaigns
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('create_campaigns')
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# COMPLIANCE_MANAGER PERMISSIONS
# ============================================================================

class CanReviewResponses(BasePermission):
    """
    Permission: review_responses
    Can review and approve assessment responses
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('review_responses')
        except TenantMembership.DoesNotExist:
            return False


class CanManageEvidence(BasePermission):
    """
    Permission: manage_evidence
    Can upload and manage evidence documents
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('manage_evidence')
        except TenantMembership.DoesNotExist:
            return False


class CanCustomizeControls(BasePermission):
    """
    Permission: customize_controls
    Can customize control descriptions
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('customize_controls')
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# EMPLOYEE PERMISSIONS
# ============================================================================

class CanViewAssignedControls(BasePermission):
    """
    Permission: view_assigned_controls
    Can view controls assigned to them
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_assigned_controls')
        except TenantMembership.DoesNotExist:
            return False


class CanSubmitResponses(BasePermission):
    """
    Permission: submit_responses
    Can submit assessment responses
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('submit_responses')
        except TenantMembership.DoesNotExist:
            return False


class CanUploadEvidence(BasePermission):
    """
    Permission: upload_evidence
    Can upload evidence for assigned controls
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('upload_evidence')
        except TenantMembership.DoesNotExist:
            return False


class CanViewOwnAssignments(BasePermission):
    """
    Permission: view_own_assignments
    Can view their own assignments
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_own_assignments')
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# AUDITOR PERMISSIONS
# ============================================================================

class CanViewFrameworks(BasePermission):
    """
    Permission: view_frameworks
    Can view all frameworks and controls
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_frameworks')
        except TenantMembership.DoesNotExist:
            return False


class CanViewResponses(BasePermission):
    """
    Permission: view_responses
    Can view all assessment responses
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_responses')
        except TenantMembership.DoesNotExist:
            return False


class CanViewEvidence(BasePermission):
    """
    Permission: view_evidence
    Can view all evidence documents
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_evidence')
        except TenantMembership.DoesNotExist:
            return False


class CanViewReports(BasePermission):
    """
    Permission: view_reports
    Can view compliance reports and analytics
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('view_reports')
        except TenantMembership.DoesNotExist:
            return False


class CanExportData(BasePermission):
    """
    Permission: export_data
    Can export compliance data
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        tenant_slug = getattr(request, 'tenant_slug', None)
        if not tenant_slug:
            return False
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                status='ACTIVE'
            )
            return membership.has_permission('export_data')
        except TenantMembership.DoesNotExist:
            return False


# ============================================================================
# OBJECT-LEVEL PERMISSIONS
# ============================================================================


# ============================================================================
# ⭐ NEW: APPROVAL WORKFLOW PERMISSIONS
# ============================================================================

class CanApproveAssignments(BasePermission):
    """
    Permission to approve control assignments
    Uses RolePermission system + separation of duties check
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # SuperAdmin bypass
        if request.user.is_superuser:
            return True
        
        # Check tenant membership exists
        if not hasattr(request, 'tenant_membership'):
            return False
        
        membership = request.tenant_membership
        
        # Check permission via RolePermission
        return membership.has_permission('approve_assignments')
    
    def has_object_permission(self, request, view, obj):
        # Cannot approve own assignment (separation of duties)
        return obj.assigned_to_user_id != request.user.id


class CanApproveResponses(BasePermission):
    """
    Permission to approve assessment responses
    Uses RolePermission system + separation of duties check
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not hasattr(request, 'tenant_membership'):
            return False
        
        membership = request.tenant_membership
        
        # Check permission via RolePermission
        return membership.has_permission('approve_responses')
    
    def has_object_permission(self, request, view, obj):
        # Cannot approve own response (separation of duties)
        return obj.responded_by_user_id != request.user.id


class CanVerifyEvidence(BasePermission):
    """
    Permission to verify evidence documents
    Uses RolePermission system + separation of duties check
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not hasattr(request, 'tenant_membership'):
            return False
        
        membership = request.tenant_membership
        
        # Check permission via RolePermission
        return membership.has_permission('verify_evidence')
    
    def has_object_permission(self, request, view, obj):
        # Cannot verify own evidence (separation of duties)
        return obj.uploaded_by_user_id != request.user.id





class IsAssignedToControl(BasePermission):
    """
    User is assigned to the specific control
    """
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        from .models import ControlAssignment
        
        return ControlAssignment.objects.filter(
            control=obj,
            assigned_to_user_id=request.user.id,
            is_active=True,
            status__in=['PENDING', 'IN_PROGRESS']
        ).exists()
"""
User Management Admin
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import Role, RolePermission, TenantMembership, TenantInvitation


# ============================================================================
# ROLE ADMIN
# ============================================================================

class RolePermissionInline(admin.TabularInline):
    """Show permissions inline with role"""
    model = RolePermission
    extra = 1
    fields = ('permission_code', 'permission_name', 'description')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_system_role', 'permission_count', 'is_active')
    list_filter = ('is_system_role', 'is_active')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at',)
    inlines = [RolePermissionInline]
    
    fieldsets = (
        ('Role Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Settings', {
            'fields': ('is_system_role', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def permission_count(self, obj):
        """Show permission count"""
        count = obj.permissions.count()
        return f"{count} permissions"
    permission_count.short_description = 'Permissions'
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system roles"""
        if obj and obj.is_system_role:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission_code', 'permission_name')
    list_filter = ('role',)
    search_fields = ('permission_code', 'permission_name', 'description')
    
    fieldsets = (
        ('Permission Details', {
            'fields': ('role', 'permission_code', 'permission_name', 'description')
        }),
    )


# ============================================================================
# TENANT MEMBERSHIP ADMIN
# ============================================================================

@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = (
        'user_display', 'tenant_slug', 'role_display',
        'status_badge', 'joined_at', 'last_activity'
    )
    list_filter = ('status', 'role', 'is_active')
    search_fields = (
        'user__username', 'user__email',
        'tenant_slug'
    )
    readonly_fields = ('joined_at', 'last_activity')
    
    fieldsets = (
        ('Membership', {
            'fields': ('user', 'tenant_slug', 'role', 'status')
        }),
        ('Metadata', {
            'fields': ('invited_by', 'invited_at', 'joined_at', 'last_activity', 'is_active')
        }),
    )
    
    # Make role a dropdown with all available roles
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = Role.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def user_display(self, obj):
        return f"{obj.user.username} ({obj.user.email})"
    user_display.short_description = 'User'
    
    def role_display(self, obj):
        return obj.role.name if obj.role else '-'
    role_display.short_description = 'Role'
    
    def status_badge(self, obj):
        colors = {
            'ACTIVE': '#10B981',
            'PENDING': '#F59E0B',
            'SUSPENDED': '#EF4444',
            'INACTIVE': '#6B7280'
        }
        from django.utils.safestring import mark_safe
        return mark_safe(
            f'<span style="background-color: {colors.get(obj.status, "#6B7280")}; '
            f'color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            f'{obj.status}</span>'
        )
    status_badge.short_description = 'Status'


# ============================================================================
# INVITATION ADMIN
# ============================================================================

@admin.register(TenantInvitation)
class TenantInvitationAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'tenant_slug', 'role_display',
        'status_badge', 'invited_by', 'created_at', 'expires_at'
    )
    list_filter = ('status', 'role')
    search_fields = ('email', 'tenant_slug')
    readonly_fields = ('token', 'created_at', 'accepted_at', 'accepted_by')
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('email', 'tenant_slug', 'role')
        }),
        ('Status', {
            'fields': ('status', 'token', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('invited_by', 'created_at', 'accepted_at', 'accepted_by')
        }),
    )
    
    # Make role a dropdown
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = Role.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def role_display(self, obj):
        return obj.role.name if obj.role else '-'
    role_display.short_description = 'Role'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': '#F59E0B',
            'ACCEPTED': '#10B981',
            'EXPIRED': '#EF4444',
            'CANCELLED': '#6B7280'
        }
        from django.utils.safestring import mark_safe
        return mark_safe(
            f'<span style="background-color: {colors.get(obj.status, "#6B7280")}; '
            f'color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            f'{obj.status}</span>'
        )
    status_badge.short_description = 'Status'


# ============================================================================
# CUSTOM USER ADMIN (Optional - shows memberships)
# ============================================================================

class TenantMembershipInline(admin.TabularInline):
    """Show user's tenant memberships inline"""
    model = TenantMembership
    fk_name = 'user'  # ← Fixes the error
    extra = 0
    fields = ('tenant_slug', 'role', 'status', 'joined_at')
    readonly_fields = ('joined_at',)
    can_delete = False


class CustomUserAdmin(BaseUserAdmin):
    """Extended user admin with tenant memberships"""
    inlines = [TenantMembershipInline]


# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


admin.site.site_header = "Compliance Platform - User Management"
admin.site.site_title = "User Admin"
admin.site.index_title = "User & Role Administration"

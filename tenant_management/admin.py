"""
Django Admin for Tenant Management
Handles tenants, subscriptions, billing, and provisioning
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.urls import reverse
from .models import (
    SubscriptionPlan, TenantDatabaseInfo, FrameworkSubscription,
    TenantUsageLog, TenantBillingHistory, SuperAdminAuditLog
)


# ============================================================================
# INLINE ADMIN CLASSES
# ============================================================================

class FrameworkSubscriptionInline(admin.TabularInline):
    model = FrameworkSubscription
    extra = 0
    fields = (
        'framework_name', 'framework_version', 'status',
        'customization_level', 'subscription_type', 'subscribed_at'
    )
    readonly_fields = ('subscribed_at',)
    can_delete = False


class TenantUsageLogInline(admin.TabularInline):
    model = TenantUsageLog
    extra = 0
    fields = (
        'log_date', 'user_count', 'framework_count',
        'control_count', 'storage_used_gb'
    )
    readonly_fields = fields
    can_delete = False
    ordering = ('-log_date',)
    
    def has_add_permission(self, request, obj=None):
        return False


# ============================================================================
# MODEL ADMIN CLASSES
# ============================================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'monthly_price_display', 'annual_price_display',
        'user_limit', 'framework_limit', 'control_limit',
        'isolation_mode_badge', 'customization_badge',
        'tenant_count', 'sort_order', 'is_active'
    )
    list_filter = ('default_isolation_mode', 'default_customization_level', 'is_active')
    search_fields = ('name', 'code', 'description')
    ordering = ('sort_order', 'monthly_price')
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('code', 'name', 'description', 'sort_order')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'annual_price')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_frameworks', 'max_controls', 'storage_gb'),
            'description': 'Set to 0 for unlimited'
        }),
        ('Features', {
            'fields': (
                'can_create_custom_frameworks', 'can_customize_controls',
                'has_api_access', 'has_advanced_reporting', 'has_sso'
            )
        }),
        ('Default Settings', {
            'fields': ('default_isolation_mode', 'default_customization_level', 'support_level')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def monthly_price_display(self, obj):
        from django.utils.safestring import mark_safe
        return mark_safe(f'<strong>${obj.monthly_price:,.2f}</strong>/mo')
    monthly_price_display.short_description = 'Monthly'
    monthly_price_display.admin_order_field = 'monthly_price'
    
    def annual_price_display(self, obj):
        from django.utils.safestring import mark_safe
        discount = ((obj.monthly_price * 12 - obj.annual_price) / (obj.monthly_price * 12) * 100)
        return mark_safe(
            f'<strong>${obj.annual_price:,.2f}</strong>/yr <span style="color: green;">({discount:.0f}% off)</span>'
        )
    annual_price_display.short_description = 'Annual'
    
    def user_limit(self, obj):
        return 'Unlimited' if obj.max_users == 0 else str(obj.max_users)
    user_limit.short_description = 'Users'
    
    def framework_limit(self, obj):
        return 'Unlimited' if obj.max_frameworks == 0 else str(obj.max_frameworks)
    framework_limit.short_description = 'Frameworks'
    
    def control_limit(self, obj):
        return 'Unlimited' if obj.max_controls == 0 else str(obj.max_controls)
    control_limit.short_description = 'Controls'
    
    def isolation_mode_badge(self, obj):
        colors = {'SCHEMA': '#3B82F6', 'DATABASE': '#10B981'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.default_isolation_mode, '#6B7280'),
            obj.default_isolation_mode
        )
    isolation_mode_badge.short_description = 'Isolation'
    
    def customization_badge(self, obj):
        colors = {'VIEW_ONLY': '#6B7280', 'CONTROL_LEVEL': '#3B82F6', 'FULL': '#10B981'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.default_customization_level, '#6B7280'),
            obj.default_customization_level
        )
    customization_badge.short_description = 'Customization'
    
    def tenant_count(self, obj):
        count = obj.tenants.filter(is_active=True).count()
        url = reverse('admin:tenant_management_tenantdatabaseinfo_changelist') + f'?subscription_plan__id__exact={obj.id}'
        return format_html('<a href="{}">{} tenants</a>', url, count)
    tenant_count.short_description = 'Tenants'


@admin.register(TenantDatabaseInfo)
class TenantDatabaseInfoAdmin(admin.ModelAdmin):
    list_display = (
        'tenant_slug', 'company_name', 'subscription_plan',
        'subscription_status_badge', 'provisioning_status_badge',
        'isolation_mode_badge', 'usage_summary',
        'is_active'
    )
    list_filter = (
        'subscription_status', 'provisioning_status',
        'isolation_mode', 'subscription_plan', 'is_active'
    )
    search_fields = ('tenant_slug', 'company_name', 'company_email')
    ordering = ('-created_at',)
    
    inlines = [FrameworkSubscriptionInline, TenantUsageLogInline]
    
    fieldsets = (
        ('Company Information', {
            'fields': ('tenant_slug', 'company_name', 'company_email', 'company_phone')
        }),
        ('Database Configuration', {
            'fields': (
                'isolation_mode', 'database_name', 'schema_name',
                'database_host', 'database_port', 'database_user', 'database_password'
            ),
            'description': 'Database connection details (password is encrypted)'
        }),
        ('Subscription', {
            'fields': (
                'subscription_plan', 'subscription_status',
                'subscription_start_date', 'subscription_end_date', 'trial_end_date'
            )
        }),
        ('Usage & Limits', {
            'fields': (
                'current_user_count', 'current_framework_count',
                'current_control_count', 'storage_used_gb'
            ),
            'classes': ('collapse',)
        }),
        ('Provisioning', {
            'fields': (
                'provisioning_status', 'provisioning_error',
                'provisioned_at', 'last_health_check'
            )
        }),
        ('Settings', {
            'fields': ('user_data_residency',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('provisioned_at', 'last_health_check', 'created_at', 'updated_at')
    
    def subscription_status_badge(self, obj):
        colors = {
            'TRIAL': '#F59E0B',
            'ACTIVE': '#10B981',
            'SUSPENDED': '#EF4444',
            'CANCELLED': '#6B7280',
            'EXPIRED': '#DC2626'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.subscription_status, '#6B7280'),
            obj.subscription_status
        )
    subscription_status_badge.short_description = 'Subscription'
    
    def provisioning_status_badge(self, obj):
        colors = {
            'PENDING': '#F59E0B',
            'PROVISIONING': '#3B82F6',
            'ACTIVE': '#10B981',
            'FAILED': '#EF4444',
            'DEPROVISIONING': '#6B7280'
        }
        icon = '✓' if obj.provisioning_status == 'ACTIVE' else '⏳' if obj.provisioning_status in ['PENDING', 'PROVISIONING'] else '✗'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{} {}</span>',
            colors.get(obj.provisioning_status, '#6B7280'),
            icon,
            obj.provisioning_status
        )
    provisioning_status_badge.short_description = 'Provisioning'
    
    def isolation_mode_badge(self, obj):
        colors = {'SCHEMA': '#3B82F6', 'DATABASE': '#10B981'}
        icon = '🗂️' if obj.isolation_mode == 'SCHEMA' else '💾'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{} {}</span>',
            colors.get(obj.isolation_mode, '#6B7280'),
            icon,
            obj.isolation_mode
        )
    isolation_mode_badge.short_description = 'Isolation'
    
    def usage_summary(self, obj):
        plan = obj.subscription_plan

        # Safely convert storage_used_gb to float
        try:
            storage_used = float(obj.storage_used_gb or 0)
        except (TypeError, ValueError):
            storage_used = 0.0

        storage_used_display = f"{storage_used:.1f}"  # <-- format here

        max_users_display = plan.max_users if plan.max_users > 0 else "∞"

        return format_html(
            '<div style="font-size: 11px;">'
            '👥 {}/{} users<br>'
            '📊 {} frameworks<br>'
            '💾 {}/{} GB'
            '</div>',
            obj.current_user_count,
            max_users_display,
            obj.current_framework_count,
            storage_used_display,   # <-- now plain {}
            plan.storage_gb,
        )


        



@admin.register(FrameworkSubscription)
class FrameworkSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'tenant', 'framework_name', 'current_version',
        'status', 'customization_level', 'subscription_type'
    )
    list_filter = (
        'status', 'customization_level',
        'subscription_type'
    )
    search_fields = (
        'tenant__company_name', 'tenant__tenant_slug',
        'framework_name'
    )
    ordering = ('-subscribed_at',)


@admin.register(TenantUsageLog)
class TenantUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        'tenant', 'log_date', 'user_count', 'framework_count',
        'control_count', 'storage_used_gb'
    )
    list_filter = ('log_date',)
    search_fields = ('tenant__company_name', 'tenant__tenant_slug')
    ordering = ('-log_date',)
    date_hierarchy = 'log_date'
    
    def has_add_permission(self, request):
        return False


@admin.register(TenantBillingHistory)
class TenantBillingHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'tenant', 'total_amount',
        'payment_status', 'billing_period_start'
    )
    list_filter = ('payment_status', 'billing_period_start')
    search_fields = ('tenant__company_name', 'invoice_number')
    ordering = ('-billing_period_start',)


@admin.register(SuperAdminAuditLog)
class SuperAdminAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp', 'admin_username', 'action',
        'tenant_slug', 'ip_address'
    )
    list_filter = ('action', 'timestamp')
    search_fields = ('admin_username', 'tenant_slug', 'ip_address')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "Compliance Platform - Tenant Management"
admin.site.site_title = "Tenant Admin"
admin.site.index_title = "Multi-Tenant Administration"

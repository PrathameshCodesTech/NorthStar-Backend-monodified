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
        'customization_badge', 'tenant_count', 'sort_order', 'is_active'
    )
    list_filter = ('default_customization_level', 'is_active', 'code')
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
            'fields': ('default_customization_level', 'support_level')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def monthly_price_display(self, obj):
        price = obj.monthly_price or 0
        price_str = "{:,.2f}".format(price)

        return format_html(
            '<span style="font-weight: 600; color: #417690;">${}</span>'
            '<span style="color: #666; font-size: 11px;">/mo</span>',
            price_str,
        )

    monthly_price_display.short_description = 'Monthly'
    monthly_price_display.admin_order_field = 'monthly_price'

    
    def annual_price_display(self, obj):
        if obj.monthly_price:
            monthly = float(obj.monthly_price)
            annual = float(obj.annual_price or 0)
            if monthly > 0:
                discount = ( (monthly * 12 - annual) / (monthly * 12) ) * 100
            else:
                discount = 0
        else:
            discount = 0

        annual_price_str = "{:,.2f}".format(obj.annual_price or 0)
        discount_str = "{:.0f}".format(discount)

        return format_html(
            '<span style="font-weight: 600; color: #417690;">${}</span>'
            '<span style="color: #666; font-size: 11px;">/yr</span> '
            '<span style="color: #28a745; font-size: 11px; font-weight: 500;">({}% off)</span>',
            annual_price_str,
            discount_str,
        )

    annual_price_display.short_description = 'Annual'

    
    def user_limit(self, obj):
        if obj.max_users == 0:
            return format_html('<span style="color: #28a745; font-weight: 500;">Unlimited</span>')
        return format_html('<span style="font-weight: 500;">{}</span>', obj.max_users)
    user_limit.short_description = 'Users'
    
    def framework_limit(self, obj):
        if obj.max_frameworks == 0:
            return format_html('<span style="color: #28a745; font-weight: 500;">Unlimited</span>')
        return format_html('<span style="font-weight: 500;">{}</span>', obj.max_frameworks)
    framework_limit.short_description = 'Frameworks'
    
    def control_limit(self, obj):
        if obj.max_controls == 0:
            return format_html('<span style="color: #28a745; font-weight: 500;">Unlimited</span>')
        return format_html('<span style="font-weight: 500;">{}</span>', obj.max_controls)
    control_limit.short_description = 'Controls'
    
    def customization_badge(self, obj):
        colors = {
            'VIEW_ONLY': '#6c757d',
            'CONTROL_LEVEL': '#417690',
            'FULL': '#28a745'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500; display: inline-block;">{}</span>',
            colors.get(obj.default_customization_level, '#6c757d'),
            obj.get_default_customization_level_display()
        )
    customization_badge.short_description = 'Customization Level'
    
    def tenant_count(self, obj):
        count = obj.tenants.filter(is_active=True).count()
        url = reverse('admin:tenant_management_tenantdatabaseinfo_changelist') + f'?subscription_plan__id__exact={obj.id}'
        return format_html(
            '<a href="{}" style="color: #417690; text-decoration: none; font-weight: 500;">{} tenant{}</a>',
            url, count, 's' if count != 1 else ''
        )
    tenant_count.short_description = 'Active Tenants'


@admin.register(TenantDatabaseInfo)
class TenantDatabaseInfoAdmin(admin.ModelAdmin):
    list_display = (
        'tenant_slug', 'company_name', 'subscription_plan',
        'subscription_status_badge', 'provisioning_status_badge',
        'schema_display', 'usage_summary', 'is_active'
    )
    list_filter = (
        'subscription_status', 'provisioning_status',
        'subscription_plan', 'is_active'
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
                'database_name', 'schema_name',
                'database_host', 'database_port', 'database_user', 'database_password'
            ),
            'description': 'Schema-based isolation: All tenants use main database with separate schemas'
        }),
        ('Subscription', {
            'fields': (
                'subscription_plan', 'subscription_status',
                'subscription_start_date', 'subscription_end_date'
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
            'PENDING_PAYMENT': '#ffc107',  # ← NEW
            'ACTIVE': '#28a745',
            'SUSPENDED': '#dc3545',
            'CANCELLED': '#6c757d',
            'EXPIRED': '#dc3545',
            'DELETED': '#000000'  # ← NEW (black)
        }
        labels = {
            'PENDING_PAYMENT': 'Pending Payment',  # ← Changed from 'Trial'
            'ACTIVE': 'Active',
            'SUSPENDED': 'Suspended',
            'CANCELLED': 'Cancelled',
            'EXPIRED': 'Expired',
            'DELETED': 'Deleted'  # ← NEW
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 3px; '
            'font-size: 11px; font-weight: 600; display: inline-block; text-transform: uppercase;">{}</span>',
            colors.get(obj.subscription_status, '#6c757d'),
            labels.get(obj.subscription_status, obj.subscription_status)
        )
    subscription_status_badge.short_description = 'Subscription'
    
    def provisioning_status_badge(self, obj):
        colors = {
            'PENDING': '#ffc107',
            'PROVISIONING': '#17a2b8',
            'ACTIVE': '#28a745',
            'FAILED': '#dc3545',
            'DEPROVISIONING': '#6c757d'
        }
        icons = {
            'PENDING': '⏳',
            'PROVISIONING': '⚙',
            'ACTIVE': '✓',
            'FAILED': '✗',
            'DEPROVISIONING': '⏳'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500; display: inline-block;">{} {}</span>',
            colors.get(obj.provisioning_status, '#6c757d'),
            icons.get(obj.provisioning_status, ''),
            obj.provisioning_status.title()
        )
    provisioning_status_badge.short_description = 'Provisioning'
    
    def schema_display(self, obj):
        return format_html(
            '<code style="background-color: #f8f9fa; padding: 3px 6px; border-radius: 3px; '
            'font-size: 11px; color: #495057; border: 1px solid #dee2e6;">{}</code>',
            obj.schema_name
        )
    schema_display.short_description = 'Schema'
    
    def usage_summary(self, obj):
        plan = obj.subscription_plan

        # Safely convert storage_used_gb to float
        try:
            storage_used = float(obj.storage_used_gb or 0)
        except (TypeError, ValueError):
            storage_used = 0.0

        # Calculate percentages
        user_percentage = (obj.current_user_count / plan.max_users * 100) if plan.max_users > 0 else 0
        framework_percentage = (obj.current_framework_count / plan.max_frameworks * 100) if plan.max_frameworks > 0 else 0
        storage_percentage = (storage_used / plan.storage_gb * 100) if plan.storage_gb > 0 else 0

        # Color based on usage
        def get_color(percentage):
            if percentage >= 90:
                return '#dc3545'
            elif percentage >= 75:
                return '#ffc107'
            else:
                return '#28a745'

        max_users_display = plan.max_users if plan.max_users > 0 else "∞"
        max_frameworks_display = plan.max_frameworks if plan.max_frameworks > 0 else "∞"
        storage_used_display = "{:.1f}".format(storage_used)

        return format_html(
            '<div style="font-size: 11px; line-height: 1.6;">'
            '<div><span style="font-weight: 600;">Users:</span> '
            '<span style="color: {};">{}/{}</span></div>'
            '<div><span style="font-weight: 600;">Frameworks:</span> '
            '<span style="color: {};">{}/{}</span></div>'
            '<div><span style="font-weight: 600;">Storage:</span> '
            '<span style="color: {};">{}/{} GB</span></div>'
            '</div>',
            get_color(user_percentage),
            obj.current_user_count,
            max_users_display,
            get_color(framework_percentage),
            obj.current_framework_count,
            max_frameworks_display,
            get_color(storage_percentage),
            storage_used_display,
            plan.storage_gb,
        )

    usage_summary.short_description = 'Current Usage'


@admin.register(FrameworkSubscription)
class FrameworkSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'tenant', 'framework_name', 'current_version',
        'status_badge', 'customization_badge', 'subscription_type',
        'subscribed_at'
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
    
    def status_badge(self, obj):
        colors = {
            'ACTIVE': '#28a745',
            'CANCELLED': '#6c757d',
            'SUSPENDED': '#ffc107'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.status.title()
        )
    status_badge.short_description = 'Status'
    
    def customization_badge(self, obj):
        colors = {
            'VIEW_ONLY': '#6c757d',
            'CONTROL_LEVEL': '#417690',
            'FULL': '#28a745'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500;">{}</span>',
            colors.get(obj.customization_level, '#6c757d'),
            obj.get_customization_level_display()
        )
    customization_badge.short_description = 'Customization'


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
        'invoice_number', 'tenant', 'total_amount_display',
        'payment_status_badge', 'billing_period_display'
    )
    list_filter = ('payment_status', 'billing_period_start')
    search_fields = ('tenant__company_name', 'invoice_number')
    ordering = ('-billing_period_start',)
    
    def total_amount_display(self, obj):
        amount = obj.total_amount or 0
        amount_str = "{:,.2f}".format(amount)

        return format_html(
            '<span style="font-weight: 600; color: #417690;">${}</span>',
            amount_str,
        )

    total_amount_display.short_description = 'Total'
    total_amount_display.admin_order_field = 'total_amount'

    
    def payment_status_badge(self, obj):
        colors = {
            'PENDING': '#ffc107',
            'PAID': '#28a745',
            'FAILED': '#dc3545',
            'REFUNDED': '#6c757d'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500;">{}</span>',
            colors.get(obj.payment_status, '#6c757d'),
            obj.payment_status.title()
        )
    payment_status_badge.short_description = 'Payment'
    
    def billing_period_display(self, obj):
        return format_html(
            '<span style="font-size: 11px;">{} to {}</span>',
            obj.billing_period_start.strftime('%b %d, %Y'),
            obj.billing_period_end.strftime('%b %d, %Y')
        )
    billing_period_display.short_description = 'Billing Period'


@admin.register(SuperAdminAuditLog)
class SuperAdminAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp', 'admin_username', 'action_display',
        'tenant_slug', 'ip_address'
    )
    list_filter = ('action', 'timestamp')
    search_fields = ('admin_username', 'tenant_slug', 'ip_address')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    def action_display(self, obj):
        colors = {
            'CREATE_TENANT': '#28a745',
            'DELETE_TENANT': '#dc3545',
            'SUSPEND_TENANT': '#ffc107',
            'VIEW_CREDENTIALS': '#17a2b8',
            'IMPERSONATE': '#ffc107',
            'QUERY_DATABASE': '#6c757d',
            'MODIFY_SUBSCRIPTION': '#417690',
            'VIEW_TENANT_DATA': '#6c757d'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; '
            'font-size: 11px; font-weight: 500;">{}</span>',
            colors.get(obj.action, '#6c757d'),
            obj.get_action_display()
        )
    action_display.short_description = 'Action'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Customize admin site branding
admin.site.site_header = "Compliance Platform Administration"
admin.site.site_title = "Tenant Admin Portal"
admin.site.index_title = "Multi-Tenant Management"
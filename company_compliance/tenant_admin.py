"""
Tenant-Specific Admin Site
Each tenant gets their own isolated admin interface
Access via: /admin/tenant/{tenant_slug}/
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.shortcuts import redirect
from django.contrib import messages
import logging


logger = logging.getLogger(__name__)

from .models import (
    CompanyFramework, CompanyDomain, CompanyCategory,
    CompanySubcategory, CompanyControl,
    ControlAssignment, AssessmentCampaign,
    AssessmentResponse, EvidenceDocument,
    ComplianceReport
)


# ============================================================================
# TENANT ADMIN SITE CLASS
# ============================================================================
class TenantAdminSite(AdminSite):
    """
    Custom admin site for tenant-specific data
    """
    site_header = "Tenant Compliance Administration"
    site_title = "Tenant Admin"
    index_title = "Compliance Management Dashboard"
    
    def __init__(self, tenant_slug, *args, **kwargs):
        self.tenant_slug = tenant_slug
        super().__init__(name=f'tenant_{tenant_slug}_admin', *args, **kwargs)
        
        # Update headers with tenant name
        from tenant_management.models import TenantDatabaseInfo
        try:
            tenant = TenantDatabaseInfo.objects.get(tenant_slug=tenant_slug)
            self.site_header = f"{tenant.company_name} - Compliance Admin"
            self.site_title = f"{tenant.company_name}"
            self.index_title = "Compliance Management Dashboard"
        except TenantDatabaseInfo.DoesNotExist:
            pass
    
    def has_permission(self, request):
        """
        Only superusers and tenant members can access
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superuser always has access
        if request.user.is_superuser:
            return True
        
        # Check if user is member of this tenant
        from user_management.models import TenantMembership
        return TenantMembership.objects.filter(
            user=request.user,
            tenant_slug=self.tenant_slug,
            status='ACTIVE',
            is_active=True
        ).exists()
    
    def admin_view(self, view, cacheable=False):
        """
        Decorator to set tenant context for all admin views
        CRITICAL: This ensures tenant_slug is set for database routing
        """
        from core.database_router import set_current_tenant, clear_current_tenant
        
        def wrapper(request, *args, **kwargs):
            # Set tenant context for database routing
            request.tenant_slug = self.tenant_slug
            set_current_tenant(self.tenant_slug)
            
            try:
                return view(request, *args, **kwargs)
            finally:
                # Don't clear - let middleware handle it
                pass
        
        # Call parent admin_view with our wrapper
        return super().admin_view(wrapper, cacheable)
    
    def index(self, request, extra_context=None):
        """
        Custom index page with tenant stats
        """
        from core.database_router import set_current_tenant
        
        # Set tenant context
        request.tenant_slug = self.tenant_slug
        set_current_tenant(self.tenant_slug)
        
        extra_context = extra_context or {}
        
        # Add tenant statistics
        try:
            frameworks_count = CompanyFramework.objects.filter(is_active=True).count()
            controls_count = CompanyControl.objects.filter(is_active=True).count()
            assignments_count = ControlAssignment.objects.filter(is_active=True).count()
            campaigns_count = AssessmentCampaign.objects.filter(is_active=True).count()
            
            extra_context.update({
                'tenant_slug': self.tenant_slug,
                'frameworks_count': frameworks_count,
                'controls_count': controls_count,
                'assignments_count': assignments_count,
                'campaigns_count': campaigns_count,
            })
        except Exception as e:
            logger.error(f"Error loading tenant stats: {e}")
            import traceback
            traceback.print_exc()
        
        return super().index(request, extra_context=extra_context)


# ============================================================================
# INLINE ADMIN CLASSES
# ============================================================================

class CompanyDomainInline(admin.TabularInline):
    model = CompanyDomain
    extra = 0
    fields = ('code', 'name', 'is_custom', 'sort_order')
    can_delete = False


class ControlAssignmentInline(admin.TabularInline):
    model = ControlAssignment
    extra = 0
    fields = ('assigned_to_username', 'status', 'priority', 'due_date')
    readonly_fields = ('assigned_to_username',)
    can_delete = False


class AssessmentResponseInline(admin.TabularInline):
    model = AssessmentResponse
    extra = 0
    fields = ('control', 'response', 'compliance_status')
    can_delete = False


# ============================================================================
# MODEL ADMIN CLASSES
# ============================================================================

class CompanyFrameworkAdmin(admin.ModelAdmin):
    """Framework admin for tenant"""
    list_display = (
        'name_display', 'version', 'status_badge',
        'customization_badge', 'domain_count',
        'control_count', 'subscribed_at'
    )
    list_filter = ('status', 'customization_level', 'is_customized')
    search_fields = ('name', 'full_name', 'description')
    ordering = ('name', '-version')
    
    inlines = [CompanyDomainInline]
    
    fieldsets = (
        ('Framework Information', {
            'fields': ('name', 'full_name', 'description', 'version', 'effective_date')
        }),
        ('Status', {
            'fields': ('status', 'customization_level', 'is_customized')
        }),
        ('Metadata', {
            'fields': ('subscribed_at', 'created_at', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('subscribed_at', 'created_at')
    
    def name_display(self, obj):
        return format_html(
            '<strong>{}</strong><br><small style="color: #6B7280;">{}</small>',
            obj.name, obj.full_name
        )
    name_display.short_description = 'Framework'
    
    def status_badge(self, obj):
        colors = {'ACTIVE': '#10B981', 'DRAFT': '#F59E0B', 'DEPRECATED': '#6B7280'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6B7280'), obj.status
        )
    status_badge.short_description = 'Status'
    
    def customization_badge(self, obj):
        colors = {'VIEW_ONLY': '#6B7280', 'CONTROL_LEVEL': '#3B82F6', 'FULL': '#10B981'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.customization_level, '#6B7280'), obj.customization_level
        )
    customization_badge.short_description = 'Customization'
    
    def domain_count(self, obj):
        count = obj.domains.filter(is_active=True).count()
        return format_html('<strong>{}</strong>', count)
    domain_count.short_description = 'Domains'
    
    def control_count(self, obj):
        count = CompanyControl.objects.filter(
            subcategory__category__domain__framework=obj,
            is_active=True
        ).count()
        return format_html('<strong>{}</strong>', count)
    control_count.short_description = 'Controls'
    
    def has_add_permission(self, request):
        return False  # Frameworks are added via API
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class CompanyControlAdmin(admin.ModelAdmin):
    """Control admin for tenant"""
    list_display = (
        'control_code', 'effective_title', 'control_type_badge',
        'risk_level_badge', 'frequency', 'is_customized_badge',
        'assignment_count'
    )
    list_filter = ('control_type', 'risk_level', 'frequency', 'is_customized')
    search_fields = ('control_code', 'title', 'custom_title', 'description')
    ordering = ('control_code',)
    
    inlines = [ControlAssignmentInline]
    
    fieldsets = (
        ('Control Information', {
            'fields': ('control_code', 'title', 'description', 'objective')
        }),
        ('Classification', {
            'fields': ('control_type', 'frequency', 'risk_level')
        }),
        ('Customization', {
            'fields': (
                'is_customized', 'custom_title',
                'custom_description', 'custom_procedures'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('control_code',)
    
    def effective_title(self, obj):
        title = obj.get_effective_title()
        if obj.is_customized:
            return format_html('✏️ <span style="color: #F59E0B;">{}</span>', title)
        return title
    effective_title.short_description = 'Title'
    
    def control_type_badge(self, obj):
        colors = {'PREVENTIVE': '#10B981', 'DETECTIVE': '#3B82F6', 'CORRECTIVE': '#F59E0B'}
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.control_type, '#6B7280'), obj.control_type
        )
    control_type_badge.short_description = 'Type'
    
    def risk_level_badge(self, obj):
        colors = {'HIGH': '#EF4444', 'MEDIUM': '#F59E0B', 'LOW': '#10B981'}
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.risk_level, '#6B7280'), obj.risk_level
        )
    risk_level_badge.short_description = 'Risk'
    
    def is_customized_badge(self, obj):
        if obj.is_customized:
            return format_html('✅ <span style="color: #10B981;">Yes</span>')
        return format_html('➖ <span style="color: #6B7280;">No</span>')
    is_customized_badge.short_description = 'Customized'
    
    def assignment_count(self, obj):
        count = obj.assignments.filter(is_active=True).count()
        return format_html('<strong>{}</strong>', count)
    assignment_count.short_description = 'Assignments'
    
    def has_add_permission(self, request):
        return False  # Controls are copied from templates
    
    def has_delete_permission(self, request, obj=None):
        return False  # Don't allow deletion


class ControlAssignmentAdmin(admin.ModelAdmin):
    """Assignment admin for tenant"""
    list_display = (
        'control_display', 'assigned_to', 'status_badge',
        'priority_badge', 'due_date', 'created_at'
    )
    list_filter = ('status', 'priority', 'due_date')
    search_fields = (
        'control__control_code', 'control__title',
        'assigned_to_username', 'notes'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Assignment', {
            'fields': ('control', 'assigned_to_username', 'assigned_to_email')
        }),
        ('Details', {
            'fields': ('status', 'priority', 'due_date', 'notes', 'completion_notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'completion_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'completion_date')
    
    def control_display(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.control.control_code,
            obj.control.title[:50] + '...' if len(obj.control.title) > 50 else obj.control.title
        )
    control_display.short_description = 'Control'
    
    def assigned_to(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.assigned_to_username,
            obj.assigned_to_email
        )
    assigned_to.short_description = 'Assigned To'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': '#F59E0B',
            'IN_PROGRESS': '#3B82F6',
            'COMPLETED': '#10B981',
            'OVERDUE': '#EF4444',
            'REJECTED': '#6B7280'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6B7280'), obj.status
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {'HIGH': '#EF4444', 'MEDIUM': '#F59E0B', 'LOW': '#10B981'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.priority, '#6B7280'), obj.priority
        )
    priority_badge.short_description = 'Priority'


class AssessmentCampaignAdmin(admin.ModelAdmin):
    """Campaign admin for tenant"""
    list_display = (
        'name', 'framework', 'status_badge',
        'date_range', 'completion_bar',
        'compliance_score_display'
    )
    list_filter = ('status', 'framework', 'start_date')
    search_fields = ('name', 'description')
    ordering = ('-start_date',)
    date_hierarchy = 'start_date'
    
    inlines = [AssessmentResponseInline]
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('framework', 'name', 'description')
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'status')
        }),
        ('Progress', {
            'fields': (
                'total_controls', 'completed_controls',
                'completion_percentage', 'compliance_score'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('total_controls', 'completed_controls', 'completion_percentage', 'compliance_score')
    
    def status_badge(self, obj):
        colors = {
            'PLANNED': '#6B7280',
            'IN_PROGRESS': '#3B82F6',
            'COMPLETED': '#10B981',
            'CANCELLED': '#EF4444'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6B7280'), obj.status
        )
    status_badge.short_description = 'Status'
    
    def date_range(self, obj):
        return format_html(
            '<small>{} → {}</small>',
            obj.start_date.strftime('%b %d, %Y'),
            obj.end_date.strftime('%b %d, %Y')
        )
    date_range.short_description = 'Period'
    
    def completion_bar(self, obj):
        percentage = float(obj.completion_percentage)
        color = '#10B981' if percentage == 100 else '#3B82F6' if percentage >= 50 else '#F59E0B'
        return format_html(
            '<div style="width: 100px; background: #E5E7EB; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; color: white; text-align: center; font-size: 11px; padding: 2px 0;">{:.0f}%</div>'
            '</div>',
            percentage, color, percentage
        )
    completion_bar.short_description = 'Completion'
    
    def compliance_score_display(self, obj):
        score = float(obj.compliance_score)
        color = '#10B981' if score >= 80 else '#F59E0B' if score >= 60 else '#EF4444'
        return format_html(
            '<strong style="color: {}; font-size: 14px;">{:.1f}%</strong>',
            color, score
        )
    compliance_score_display.short_description = 'Compliance'


class AssessmentResponseAdmin(admin.ModelAdmin):
    """Response admin for tenant"""
    list_display = (
        'campaign', 'control_display', 'response_badge',
        'compliance_badge', 'responded_by', 'responded_at'
    )
    list_filter = ('response', 'compliance_status', 'campaign')
    search_fields = ('control__control_code', 'notes', 'responded_by_username')
    ordering = ('-responded_at',)
    date_hierarchy = 'responded_at'
    
    fieldsets = (
        ('Assessment', {
            'fields': ('campaign', 'control', 'assignment')
        }),
        ('Response', {
            'fields': ('response', 'compliance_status', 'confidence_level', 'notes')
        }),
        ('Metadata', {
            'fields': ('responded_by_username', 'responded_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('responded_at',)
    
    def control_display(self, obj):
        return obj.control.control_code
    control_display.short_description = 'Control'
    
    def response_badge(self, obj):
        colors = {
            'COMPLIANT': '#10B981',
            'NON_COMPLIANT': '#EF4444',
            'PARTIAL': '#F59E0B',
            'NOT_APPLICABLE': '#6B7280',
            'PENDING': '#3B82F6'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.response, '#6B7280'), obj.response
        )
    response_badge.short_description = 'Response'
    
    def compliance_badge(self, obj):
        if not obj.compliance_status:
            return '-'
        colors = {'PASS': '#10B981', 'FAIL': '#EF4444', 'PARTIAL': '#F59E0B', 'N/A': '#6B7280'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.compliance_status, '#6B7280'), obj.compliance_status
        )
    compliance_badge.short_description = 'Compliance'
    
    def responded_by(self, obj):
        return obj.responded_by_username
    responded_by.short_description = 'Responded By'


class EvidenceDocumentAdmin(admin.ModelAdmin):
    """Evidence admin for tenant"""
    list_display = (
        'title', 'control', 'file_type_badge',
        'file_size_display', 'verified_badge',
        'uploaded_by', 'uploaded_at'
    )
    list_filter = ('file_extension', 'is_verified', 'uploaded_at')
    search_fields = ('title', 'file_name', 'control__control_code')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Document', {
            'fields': ('control', 'title', 'description')
        }),
        ('File', {
            'fields': ('file_name', 'file_path', 'file_size', 'file_type')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_archived')
        }),
        ('Metadata', {
            'fields': ('uploaded_by_username', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('file_size', 'file_type', 'uploaded_at')
    
    def file_type_badge(self, obj):
        colors = {
            'pdf': '#EF4444', 'doc': '#3B82F6', 'docx': '#3B82F6',
            'xls': '#10B981', 'xlsx': '#10B981',
            'png': '#8B5CF6', 'jpg': '#8B5CF6', 'jpeg': '#8B5CF6'
        }
        ext = obj.file_extension.lower().strip('.')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(ext, '#6B7280'), ext.upper()
        )
    file_type_badge.short_description = 'Type'
    
    def file_size_display(self, obj):
        size_kb = obj.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        return f"{size_kb / 1024:.1f} MB"
    file_size_display.short_description = 'Size'
    
    def verified_badge(self, obj):
        if obj.is_verified:
            return format_html('✅ <span style="color: #10B981;">Verified</span>')
        return format_html('⏳ <span style="color: #F59E0B;">Pending</span>')
    verified_badge.short_description = 'Status'
    
    def uploaded_by(self, obj):
        return obj.uploaded_by_username
    uploaded_by.short_description = 'Uploaded By'


class ComplianceReportAdmin(admin.ModelAdmin):
    """Report admin for tenant"""
    list_display = (
        'title', 'report_type_badge', 'framework',
        'compliance_display', 'status_badges',
        'generated_at'
    )
    list_filter = ('report_type', 'is_final', 'is_published')
    search_fields = ('title', 'description')
    ordering = ('-generated_at',)
    date_hierarchy = 'generated_at'
    
    fieldsets = (
        ('Report', {
            'fields': ('framework', 'campaign', 'title', 'description', 'report_type')
        }),
        ('Metrics', {
            'fields': (
                'overall_compliance_score', 'total_controls',
                'compliant_controls', 'non_compliant_controls'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_final', 'is_published')
        }),
        ('Metadata', {
            'fields': ('generated_by_username', 'generated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('generated_at',)
    
    def report_type_badge(self, obj):
        colors = {
            'SUMMARY': '#3B82F6', 'DETAILED': '#10B981',
            'EXECUTIVE': '#8B5CF6', 'AUDIT': '#EF4444',
            'GAP_ANALYSIS': '#F59E0B'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.report_type, '#6B7280'), obj.report_type
        )
    report_type_badge.short_description = 'Type'
    
    def compliance_display(self, obj):
        score = float(obj.overall_compliance_score)
        color = '#10B981' if score >= 80 else '#F59E0B' if score >= 60 else '#EF4444'
        return format_html(
            '<strong style="color: {}; font-size: 14px;">{:.1f}%</strong>',
            color, score
        )
    compliance_display.short_description = 'Score'
    
    def status_badges(self, obj):
        badges = []
        if obj.is_final:
            badges.append('<span style="background: #10B981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">FINAL</span>')
        if obj.is_published:
            badges.append('<span style="background: #3B82F6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">PUBLISHED</span>')
        return format_html(' '.join(badges)) if badges else '-'
    status_badges.short_description = 'Status'


# ============================================================================
# TENANT ADMIN SITE FACTORY
# ============================================================================

def create_tenant_admin_site(tenant_slug):
    """
    Factory function to create a tenant-specific admin site
    """
    # Create the admin site
    tenant_admin = TenantAdminSite(tenant_slug)
    
    # Register models
    tenant_admin.register(CompanyFramework, CompanyFrameworkAdmin)
    tenant_admin.register(CompanyControl, CompanyControlAdmin)
    tenant_admin.register(ControlAssignment, ControlAssignmentAdmin)
    tenant_admin.register(AssessmentCampaign, AssessmentCampaignAdmin)
    tenant_admin.register(AssessmentResponse, AssessmentResponseAdmin)
    tenant_admin.register(EvidenceDocument, EvidenceDocumentAdmin)
    tenant_admin.register(ComplianceReport, ComplianceReportAdmin)
    
    return tenant_admin
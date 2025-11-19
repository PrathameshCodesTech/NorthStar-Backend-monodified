# """
# Django Admin for Company Compliance
# NOTE: This admin should be tenant-aware - only show data for selected tenant
# This is a simplified version; full implementation requires tenant context middleware
# """

# from django.contrib import admin
# from django.utils.html import format_html
# from django.db.models import Count
# from .models import (
#     CompanyFramework, CompanyDomain, CompanyCategory,
#     CompanySubcategory, CompanyControl,
#     CompanyAssessmentQuestion, CompanyEvidenceRequirement,
#     ControlAssignment, AssessmentCampaign, AssessmentResponse,
#     EvidenceDocument, ComplianceReport
# )


# # ============================================================================
# # INLINE ADMIN CLASSES
# # ============================================================================

# class CompanyDomainInline(admin.TabularInline):
#     model = CompanyDomain
#     extra = 0
#     fields = ('code', 'name', 'is_custom', 'sort_order')
#     readonly_fields = ('template_domain_id',)


# class CompanyCategoryInline(admin.TabularInline):
#     model = CompanyCategory
#     extra = 0
#     fields = ('code', 'name', 'is_custom', 'sort_order')


# class CompanySubcategoryInline(admin.TabularInline):
#     model = CompanySubcategory
#     extra = 0
#     fields = ('code', 'name', 'is_custom', 'sort_order')


# class CompanyControlInline(admin.TabularInline):
#     model = CompanyControl
#     extra = 0
#     fields = ('control_code', 'title', 'is_customized', 'control_type', 'risk_level')
#     show_change_link = True


# class ControlAssignmentInline(admin.TabularInline):
#     model = ControlAssignment
#     extra = 0
#     fields = ('assigned_to_username', 'status', 'priority', 'due_date')
#     readonly_fields = ('assigned_to_username',)


# class AssessmentResponseInline(admin.TabularInline):
#     model = AssessmentResponse
#     extra = 0
#     fields = ('control', 'response', 'compliance_status', 'responded_by_username')
#     readonly_fields = ('responded_by_username',)


# # ============================================================================
# # MODEL ADMIN CLASSES
# # ============================================================================

# @admin.register(CompanyFramework)
# class CompanyFrameworkAdmin(admin.ModelAdmin):
#     list_display = (
#         'name', 'version', 'status', 'customization_level',
#         'is_customized', 'is_template_synced', 'subscribed_at'
#     )
#     list_filter = ('status', 'customization_level', 'is_customized', 'is_template_synced')
#     search_fields = ('name', 'full_name', 'description')
#     ordering = ('name', '-version')
    
#     inlines = [CompanyDomainInline]
    
#     fieldsets = (
#         ('Framework', {
#             'fields': ('name', 'full_name', 'description', 'version', 'effective_date', 'status')
#         }),
#         ('Template Link', {
#             'fields': ('template_framework_id', 'is_template_synced')
#         }),
#         ('Customization', {
#             'fields': ('customization_level', 'is_customized', 'custom_description')
#         }),
#         ('Metadata', {
#             'fields': ('subscribed_at', 'created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('subscribed_at', 'created_at', 'updated_at')


# @admin.register(CompanyControl)
# class CompanyControlAdmin(admin.ModelAdmin):
#     list_display = (
#         'control_code', 'effective_title', 'control_type',
#         'frequency', 'risk_level', 'is_customized',
#         'assignment_count', 'is_active'
#     )
#     list_filter = (
#         'control_type', 'frequency', 'risk_level',
#         'is_customized', 'can_customize', 'is_active'
#     )
#     search_fields = ('control_code', 'title', 'custom_title', 'description')
#     ordering = ('subcategory', 'sort_order', 'control_code')
    
#     inlines = [ControlAssignmentInline]
    
#     fieldsets = (
#         ('Control', {
#             'fields': ('subcategory', 'control_code', 'title', 'description', 'objective')
#         }),
#         ('Classification', {
#             'fields': ('control_type', 'frequency', 'risk_level', 'sort_order')
#         }),
#         ('Customization', {
#             'fields': (
#                 'template_control_id', 'is_customized', 'can_customize',
#                 'custom_title', 'custom_description', 'custom_objective', 'custom_procedures',
#                 'customized_at', 'customized_by_user_id'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('customized_at', 'created_at', 'updated_at')
    
#     def effective_title(self, obj):
#         title = obj.get_effective_title()
#         if obj.is_customized:
#             return format_html('<span style="color: #F59E0B;">✏️ {}</span>', title)
#         return title
#     effective_title.short_description = 'Title'
    
#     def assignment_count(self, obj):
#         count = obj.assignments.filter(is_active=True).count()
#         return format_html('<strong>{}</strong>', count)
#     assignment_count.short_description = 'Assignments'


# @admin.register(ControlAssignment)
# class ControlAssignmentAdmin(admin.ModelAdmin):
#     list_display = (
#         'control', 'assigned_to_username', 'status',
#         'priority', 'due_date', 'completion_date',
#         'notification_status', 'created_at'
#     )
#     list_filter = ('status', 'priority', 'due_date', 'notification_sent')
#     search_fields = (
#         'control__control_code', 'control__title',
#         'assigned_to_username', 'assigned_to_email'
#     )
#     ordering = ('-created_at',)
    
#     fieldsets = (
#         ('Assignment', {
#             'fields': ('control', 'assigned_to_user_id', 'assigned_to_username', 'assigned_to_email')
#         }),
#         ('Details', {
#             'fields': ('status', 'priority', 'due_date', 'completion_date', 'notes', 'completion_notes')
#         }),
#         ('Notifications', {
#             'fields': ('notification_sent', 'reminder_sent'),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('assigned_by_user_id', 'created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('created_at', 'updated_at')
    
#     def notification_status(self, obj):
#         icons = []
#         if obj.notification_sent:
#             icons.append('📧')
#         if obj.reminder_sent:
#             icons.append('🔔')
#         return ' '.join(icons) if icons else '-'
#     notification_status.short_description = 'Notifications'


# @admin.register(AssessmentCampaign)
# class AssessmentCampaignAdmin(admin.ModelAdmin):
#     list_display = (
#         'name', 'framework', 'status', 'start_date', 'end_date',
#         'completion_display', 'compliance_display', 'created_by_username'
#     )
#     list_filter = ('status', 'framework', 'start_date')
#     search_fields = ('name', 'description', 'framework__name')
#     ordering = ('-start_date',)
#     date_hierarchy = 'start_date'
    
#     inlines = [AssessmentResponseInline]
    
#     fieldsets = (
#         ('Campaign', {
#             'fields': ('framework', 'name', 'description', 'created_by_username')
#         }),
#         ('Timeline', {
#             'fields': ('start_date', 'end_date', 'status')
#         }),
#         ('Progress', {
#             'fields': (
#                 'total_controls', 'completed_controls', 'completion_percentage',
#                 'compliant_count', 'non_compliant_count', 'not_applicable_count',
#                 'compliance_score'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('created_at', 'updated_at')
    
#     def completion_display(self, obj):
#         percentage = obj.completion_percentage
#         color = '#10B981' if percentage == 100 else '#F59E0B' if percentage >= 50 else '#EF4444'
#         return format_html(
#             '<div style="width: 100px; background-color: #E5E7EB; border-radius: 3px; overflow: hidden;">'
#             '<div style="width: {}%; background-color: {}; color: white; text-align: center; font-size: 11px; padding: 2px 0;">{:.0f}%</div>'
#             '</div>',
#             percentage, color, percentage
#         )
#     completion_display.short_description = 'Completion'
    
#     def compliance_display(self, obj):
#         score = obj.compliance_score
#         color = '#10B981' if score >= 80 else '#F59E0B' if score >= 60 else '#EF4444'
#         return format_html(
#             '<strong style="color: {};">{:.1f}%</strong> ({}/{})',
#             color, score, obj.compliant_count, obj.compliant_count + obj.non_compliant_count
#         )
#     compliance_display.short_description = 'Compliance'


# @admin.register(AssessmentResponse)
# class AssessmentResponseAdmin(admin.ModelAdmin):
#     list_display = (
#         'campaign', 'control', 'response', 'compliance_status',
#         'confidence_level', 'remediation_required',
#         'responded_by_username', 'responded_at'
#     )
#     list_filter = (
#         'response', 'compliance_status', 'confidence_level',
#         'remediation_required', 'campaign'
#     )
#     search_fields = (
#         'control__control_code', 'control__title',
#         'responded_by_username', 'notes'
#     )
#     ordering = ('-responded_at',)
    
#     fieldsets = (
#         ('Assessment', {
#             'fields': ('campaign', 'control', 'assignment')
#         }),
#         ('Response', {
#             'fields': (
#                 'response', 'compliance_status', 'confidence_level',
#                 'notes', 'issues_identified'
#             )
#         }),
#         ('Remediation', {
#             'fields': ('remediation_required', 'remediation_plan'),
#             'classes': ('collapse',)
#         }),
#         ('Respondent', {
#             'fields': ('responded_by_user_id', 'responded_by_username', 'responded_at'),
#             'classes': ('collapse',)
#         }),
#         ('Review', {
#             'fields': ('reviewed_by_user_id', 'reviewed_at', 'review_notes'),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('responded_at', 'reviewed_at', 'created_at', 'updated_at')


# @admin.register(EvidenceDocument)
# class EvidenceDocumentAdmin(admin.ModelAdmin):
#     list_display = (
#         'title', 'control', 'file_name', 'file_type_badge',
#         'file_size_display', 'is_verified', 'uploaded_by_username',
#         'uploaded_at', 'is_archived'
#     )
#     list_filter = (
#         'file_extension', 'is_verified', 'is_archived',
#         'uploaded_at'
#     )
#     search_fields = (
#         'title', 'file_name', 'control__control_code',
#         'uploaded_by_username', 'tags'
#     )
#     ordering = ('-uploaded_at',)
#     date_hierarchy = 'uploaded_at'
    
#     fieldsets = (
#         ('Document', {
#             'fields': ('control', 'response', 'title', 'description', 'tags')
#         }),
#         ('File', {
#             'fields': (
#                 'file_name', 'file_path', 'file_size',
#                 'file_type', 'file_extension'
#             )
#         }),
#         ('Upload Info', {
#             'fields': ('uploaded_by_user_id', 'uploaded_by_username', 'uploaded_at'),
#             'classes': ('collapse',)
#         }),
#         ('Verification', {
#             'fields': ('is_verified', 'verified_by_user_id', 'verified_at'),
#             'classes': ('collapse',)
#         }),
#         ('Archive', {
#             'fields': ('is_archived', 'archived_at'),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('uploaded_at', 'verified_at', 'archived_at', 'created_at', 'updated_at')
    
#     def file_type_badge(self, obj):
#         colors = {
#             'pdf': '#EF4444',
#             'doc': '#3B82F6',
#             'docx': '#3B82F6',
#             'xls': '#10B981',
#             'xlsx': '#10B981',
#             'png': '#8B5CF6',
#             'jpg': '#8B5CF6',
#             'jpeg': '#8B5CF6'
#         }
#         color = colors.get(obj.file_extension.lower().strip('.'), '#6B7280')
#         return format_html(
#             '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
#             color, obj.file_extension.upper()
#         )
#     file_type_badge.short_description = 'Type'
    
#     def file_size_display(self, obj):
#         size_kb = obj.file_size / 1024
#         if size_kb < 1024:
#             return f"{size_kb:.1f} KB"
#         else:
#             size_mb = size_kb / 1024
#             return f"{size_mb:.1f} MB"
#     file_size_display.short_description = 'Size'


# @admin.register(ComplianceReport)
# class ComplianceReportAdmin(admin.ModelAdmin):
#     list_display = (
#         'title', 'framework', 'report_type', 'report_format',
#         'compliance_score_display', 'is_final', 'is_published',
#         'generated_by_username', 'generated_at'
#     )
#     list_filter = (
#         'report_type', 'report_format', 'is_final',
#         'is_published', 'generated_at'
#     )
#     search_fields = ('title', 'description', 'framework__name')
#     ordering = ('-generated_at',)
#     date_hierarchy = 'generated_at'
    
#     fieldsets = (
#         ('Report', {
#             'fields': ('framework', 'campaign', 'title', 'description', 'report_type', 'report_format')
#         }),
#         ('File', {
#             'fields': ('file_path', 'file_size')
#         }),
#         ('Compliance Metrics', {
#             'fields': (
#                 'overall_compliance_score', 'total_controls',
#                 'compliant_controls', 'non_compliant_controls',
#                 'not_applicable_controls'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Period', {
#             'fields': ('report_period_start', 'report_period_end'),
#             'classes': ('collapse',)
#         }),
#         ('Status', {
#             'fields': ('is_final', 'is_published')
#         }),
#         ('Generator', {
#             'fields': ('generated_by_user_id', 'generated_by_username', 'generated_at'),
#             'classes': ('collapse',)
#         }),
#         ('Metadata', {
#             'fields': ('created_at', 'updated_at', 'is_active'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     readonly_fields = ('generated_at', 'created_at', 'updated_at')
    
#     def compliance_score_display(self, obj):
#         score = obj.overall_compliance_score
#         color = '#10B981' if score >= 80 else '#F59E0B' if score >= 60 else '#EF4444'
#         return format_html(
#             '<strong style="color: {}; font-size: 14px;">{:.1f}%</strong>',
#             color, score
#         )
#     compliance_score_display.short_description = 'Compliance'





# # ============================================================================
# # ADMIN SITE CUSTOMIZATION
# # ============================================================================

# admin.site.site_header = "Compliance Platform - Company Compliance"
# admin.site.site_title = "Company Admin"
# admin.site.index_title = "Tenant Compliance Management"

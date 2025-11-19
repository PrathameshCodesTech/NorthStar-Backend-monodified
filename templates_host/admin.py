"""
Django Admin for Templates App - Service 1
Manage compliance framework templates
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import (
    Framework, Domain, Category, Subcategory,
    Control, AssessmentQuestion, EvidenceRequirement
)


class DomainInline(admin.TabularInline):
    """Inline admin for domains within framework"""
    model = Domain
    extra = 0
    fields = ['code', 'name', 'sort_order', 'is_active']
    show_change_link = True


class CategoryInline(admin.TabularInline):
    """Inline admin for categories within domain"""
    model = Category
    extra = 0
    fields = ['code', 'name', 'sort_order', 'is_active']
    show_change_link = True


class SubcategoryInline(admin.TabularInline):
    """Inline admin for subcategories within category"""
    model = Subcategory
    extra = 0
    fields = ['code', 'name', 'sort_order', 'is_active']
    show_change_link = True


class ControlInline(admin.TabularInline):
    """Inline admin for controls within subcategory"""
    model = Control
    extra = 0
    fields = ['control_code', 'title', 'control_type', 'risk_level', 'is_active']
    show_change_link = True


class AssessmentQuestionInline(admin.TabularInline):
    """Inline admin for questions within control"""
    model = AssessmentQuestion
    extra = 0
    fields = ['question_type', 'question', 'is_mandatory', 'sort_order']
    show_change_link = True


class EvidenceRequirementInline(admin.TabularInline):
    """Inline admin for evidence requirements within control"""
    model = EvidenceRequirement
    extra = 0
    fields = ['title', 'evidence_type', 'is_mandatory', 'sort_order']
    show_change_link = True


@admin.register(Framework)
class FrameworkAdmin(admin.ModelAdmin):
    """Admin interface for managing frameworks"""
    
    list_display = [
        'name_display',
        'version',
        'status_badge',
        'effective_date',
        'domain_count',
        'control_count',
        'created_at'
    ]
    
    list_filter = ['status', 'effective_date', 'is_active']
    
    search_fields = ['name', 'full_name', 'version']
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'hierarchy_summary'
    ]
    
    fieldsets = (
        ('Framework Information', {
            'fields': (
                'id',
                'name',
                'full_name',
                'version',
                'description'
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'effective_date',
                'is_active'
            )
        }),
        ('Hierarchy Summary', {
            'fields': ('hierarchy_summary',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'updated_at',
                'created_by',
                'updated_by'
            )
        })
    )
    
    inlines = [DomainInline]
    
    ordering = ['name', '-version']
    
    def name_display(self, obj):
        """Display framework name with full name"""
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.name,
            obj.full_name
        )
    name_display.short_description = 'Framework'
    
    def status_badge(self, obj):
        """Display status with color"""
        colors = {
            'ACTIVE': 'green',
            'DRAFT': 'orange',
            'DEPRECATED': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.status
        )
    status_badge.short_description = 'Status'
    
    def domain_count(self, obj):
        """Count of domains"""
        count = obj.domains.filter(is_active=True).count()
        return format_html(
            '<span style="background: #007bff; color: white; padding: 2px 8px; '
            'border-radius: 3px;">{}</span>',
            count
        )
    domain_count.short_description = 'Domains'
    
    def control_count(self, obj):
        """Count of all controls in framework"""
        count = Control.objects.filter(
            subcategory__category__domain__framework=obj,
            is_active=True
        ).count()
        return format_html(
            '<span style="background: #28a745; color: white; padding: 2px 8px; '
            'border-radius: 3px;">{}</span>',
            count
        )
    control_count.short_description = 'Controls'
    
    def hierarchy_summary(self, obj):
        """Display complete hierarchy summary"""
        if obj and obj.pk:
            domains = obj.domains.filter(is_active=True)
            summary = []
            for domain in domains:
                categories = domain.categories.filter(is_active=True)
                summary.append(f'<strong>📁 {domain.code} - {domain.name}</strong> ({categories.count()} categories)')
                for category in categories:
                    subcategories = category.subcategories.filter(is_active=True)
                    summary.append(f'  └─ 📂 {category.code} - {category.name} ({subcategories.count()} subcategories)')
                    for subcategory in subcategories:
                        controls = subcategory.controls.filter(is_active=True)
                        summary.append(f'      └─ 📄 {subcategory.code} - {subcategory.name} ({controls.count()} controls)')
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; '
                'font-family: monospace; font-size: 12px; white-space: pre-line;">{}</div>',
                '\n'.join(summary) if summary else 'No hierarchy yet'
            )
        return "Save framework first"
    hierarchy_summary.short_description = 'Framework Hierarchy'


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    """Admin interface for managing domains"""
    
    list_display = [
        'code',
        'name',
        'framework_display',
        'category_count',
        'sort_order',
        'is_active'
    ]
    
    list_filter = ['framework', 'is_active']
    
    search_fields = ['code', 'name', 'framework__name']
    
    autocomplete_fields = ['framework']
    
    inlines = [CategoryInline]
    
    ordering = ['framework', 'sort_order']
    
    def framework_display(self, obj):
        """Display framework name"""
        return f"{obj.framework.name} v{obj.framework.version}" if obj.framework else '-'
    framework_display.short_description = 'Framework'
    
    def category_count(self, obj):
        """Count of categories"""
        return obj.categories.filter(is_active=True).count()
    category_count.short_description = 'Categories'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for managing categories"""
    
    list_display = [
        'code',
        'name',
        'domain_display',
        'subcategory_count',
        'sort_order',
        'is_active'
    ]
    
    list_filter = ['domain__framework', 'domain', 'is_active']
    
    search_fields = ['code', 'name', 'domain__name']
    
    autocomplete_fields = ['domain']
    
    inlines = [SubcategoryInline]
    
    ordering = ['domain', 'sort_order']
    
    def domain_display(self, obj):
        """Display domain and framework"""
        if obj.domain:
            return f"{obj.domain.code} ({obj.domain.framework.name})"
        return '-'
    domain_display.short_description = 'Domain'
    
    def subcategory_count(self, obj):
        """Count of subcategories"""
        return obj.subcategories.filter(is_active=True).count()
    subcategory_count.short_description = 'Subcategories'


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    """Admin interface for managing subcategories"""
    
    list_display = [
        'code',
        'name',
        'category_display',
        'control_count',
        'sort_order',
        'is_active'
    ]
    
    list_filter = [
        'category__domain__framework',
        'category__domain',
        'category',
        'is_active'
    ]
    
    search_fields = ['code', 'name', 'category__name']
    
    autocomplete_fields = ['category']
    
    inlines = [ControlInline]
    
    ordering = ['category', 'sort_order']
    
    def category_display(self, obj):
        """Display category and hierarchy"""
        if obj.category:
            return f"{obj.category.code} > {obj.category.domain.code}"
        return '-'
    category_display.short_description = 'Category'
    
    def control_count(self, obj):
        """Count of controls"""
        return obj.controls.filter(is_active=True).count()
    control_count.short_description = 'Controls'


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    """Admin interface for managing controls"""
    
    list_display = [
        'control_code',
        'title_short',
        'control_type_badge',
        'frequency_badge',
        'risk_level_badge',
        'question_count',
        'evidence_count',
        'is_active'
    ]
    
    list_filter = [
        'control_type',
        'frequency',
        'risk_level',
        'subcategory__category__domain__framework',
        'is_active'
    ]
    
    search_fields = [
        'control_code',
        'title',
        'description',
        'subcategory__name'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'full_hierarchy_display'
    ]
    
    autocomplete_fields = ['subcategory']
    
    fieldsets = (
        ('Control Information', {
            'fields': (
                'id',
                'subcategory',
                'control_code',
                'title',
                'description',
                'objective'
            )
        }),
        ('Classification', {
            'fields': (
                'control_type',
                'frequency',
                'risk_level',
                'sort_order'
            )
        }),
        ('Hierarchy', {
            'fields': ('full_hierarchy_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'is_active',
                'created_at',
                'updated_at',
                'created_by',
                'updated_by'
            )
        })
    )
    
    inlines = [AssessmentQuestionInline, EvidenceRequirementInline]
    
    ordering = ['subcategory', 'sort_order', 'control_code']
    
    def title_short(self, obj):
        """Truncated title"""
        if len(obj.title) > 60:
            return obj.title[:60] + '...'
        return obj.title
    title_short.short_description = 'Title'
    
    def control_type_badge(self, obj):
        """Display control type as badge"""
        colors = {
            'PREVENTIVE': '#28a745',
            'DETECTIVE': '#007bff',
            'CORRECTIVE': '#ffc107'
        }
        color = colors.get(obj.control_type, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.control_type
        )
    control_type_badge.short_description = 'Type'
    
    def frequency_badge(self, obj):
        """Display frequency as badge"""
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            obj.frequency
        )
    frequency_badge.short_description = 'Frequency'
    
    def risk_level_badge(self, obj):
        """Display risk level as badge"""
        colors = {
            'HIGH': '#dc3545',
            'MEDIUM': '#fd7e14',
            'LOW': '#28a745'
        }
        color = colors.get(obj.risk_level, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.risk_level
        )
    risk_level_badge.short_description = 'Risk'
    
    def question_count(self, obj):
        """Count of assessment questions"""
        return obj.assessment_questions.count()
    question_count.short_description = 'Questions'
    
    def evidence_count(self, obj):
        """Count of evidence requirements"""
        return obj.evidence_requirements.count()
    evidence_count.short_description = 'Evidence'
    
    def full_hierarchy_display(self, obj):
        """Display full hierarchy path"""
        if obj and obj.subcategory:
            subcat = obj.subcategory
            cat = subcat.category
            dom = cat.domain if cat else None
            fw = dom.framework if dom else None
            
            return format_html(
                '<div style="background: #e7f3ff; padding: 15px; border-radius: 5px;">'
                '<strong>🏢 Framework:</strong> {} v{}<br>'
                '<strong>📁 Domain:</strong> {} - {}<br>'
                '<strong>📂 Category:</strong> {} - {}<br>'
                '<strong>📄 Subcategory:</strong> {} - {}<br>'
                '<strong>✓ Control:</strong> {} - {}'
                '</div>',
                fw.name if fw else 'N/A',
                fw.version if fw else 'N/A',
                dom.code if dom else 'N/A',
                dom.name if dom else 'N/A',
                cat.code if cat else 'N/A',
                cat.name if cat else 'N/A',
                subcat.code,
                subcat.name,
                obj.control_code,
                obj.title
            )
        return "No hierarchy"
    full_hierarchy_display.short_description = 'Hierarchy Path'


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    """Admin interface for managing assessment questions"""
    
    list_display = [
        'control_code_display',
        'question_short',
        'question_type',
        'is_mandatory',
        'sort_order'
    ]
    
    list_filter = ['question_type', 'is_mandatory', 'control__subcategory__category__domain__framework']
    
    search_fields = ['question', 'control__control_code', 'control__title']
    
    autocomplete_fields = ['control']
    
    ordering = ['control', 'sort_order']
    
    def control_code_display(self, obj):
        """Display control code"""
        return obj.control.control_code if obj.control else '-'
    control_code_display.short_description = 'Control'
    
    def question_short(self, obj):
        """Truncated question"""
        if len(obj.question) > 80:
            return obj.question[:80] + '...'
        return obj.question
    question_short.short_description = 'Question'


@admin.register(EvidenceRequirement)
class EvidenceRequirementAdmin(admin.ModelAdmin):
    """Admin interface for managing evidence requirements"""
    
    list_display = [
        'control_code_display',
        'title',
        'evidence_type',
        'is_mandatory',
        'file_format',
        'sort_order'
    ]
    
    list_filter = ['evidence_type', 'is_mandatory', 'control__subcategory__category__domain__framework']
    
    search_fields = ['title', 'control__control_code', 'description']
    
    autocomplete_fields = ['control']
    
    ordering = ['control', 'sort_order']
    
    def control_code_display(self, obj):
        """Display control code"""
        return obj.control.control_code if obj.control else '-'
    control_code_display.short_description = 'Control'
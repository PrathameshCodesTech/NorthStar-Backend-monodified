"""
Models for Template Service - Compliance Framework Management
"""

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid
from datetime import date
# from ..scripts.tenant_models import TenantDatabaseInfo

class BaseModel(models.Model):
    """Abstract base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, default='system')
    updated_by = models.CharField(max_length=100, default='system')
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Framework(BaseModel):
    """Top level - SOX, ISO 27001, NIST, etc."""
    
    name = models.CharField(
        max_length=50, 
        help_text="Short name like 'SOX', 'ISO27001'"
    )
    full_name = models.CharField(
        max_length=200,
        help_text="Full name like 'Sarbanes-Oxley Act'"
    )
    description = models.TextField(blank=True)
    version = models.CharField(
        max_length=20,
        default="1.0",
        help_text="Version like '2024.1', '2022.1'"
    )
    effective_date = models.DateField(
    default=date.today,
    help_text="When this framework version becomes effective"
)
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('ACTIVE', 'Active'),
            ('DEPRECATED', 'Deprecated'),
            ('SUPERSEDED', 'Superseded'), 
        ],
        default='DRAFT'
    )

     # ============ NEW FIELDS ADDED ============
    category = models.ForeignKey(
        'FrameworkCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='frameworks',
        help_text="Category (Financial, Security, Privacy, etc.)"
    )
    applicable_industries = models.JSONField(
        default=list,
        blank=True,
        help_text="Industries this applies to - ['Finance', 'Healthcare', 'Technology']"
    )
    applicable_regions = models.JSONField(
        default=list,
        blank=True,
        help_text="Regions this applies to - ['US', 'EU', 'Global', 'APAC']"
    )
    compliance_authority = models.CharField(
        max_length=100,
        blank=True,
        help_text="Governing body (e.g., 'SEC', 'ISO', 'GDPR Authority', 'HIPAA')"
    )
    is_current_version = models.BooleanField(
        default=True,
        help_text="Is this the latest/current version of the framework?"
    )
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supersedes',
        help_text="If deprecated, which version replaced this?"
    )
    changelog = models.TextField(
        blank=True,
        help_text="What changed in this version compared to previous"
    )
    # ==========================================
    
    class Meta:
        db_table = 'frameworks'
        ordering = ['name', 'version']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'version'], 
                name='unique_framework_name_version'
            )
        ]
        
    def __str__(self):
        return f"{self.name} v{self.version}"



class Domain(BaseModel):
    """Second level - IT General Controls, Application Controls, etc."""
    
    framework = models.ForeignKey(
        Framework,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='domains'
    )

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'ITGC', 'BPC'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
            db_table = 'domains'
            ordering = ['framework', 'sort_order', 'name']
            constraints = [
                models.UniqueConstraint(
                    fields=['framework', 'code'],
                    condition=models.Q(framework__isnull=False),
                    name='unique_domain_code_per_framework'
                ),
                models.UniqueConstraint(
                    fields=['framework', 'name'],
                    condition=models.Q(framework__isnull=False),
                    name='unique_domain_name_per_framework'
                )
            ]
        
    def __str__(self):
        fw_name = self.framework.name if self.framework_id else 'Unlinked'
        return f"{fw_name} - {self.name}"


class Category(BaseModel):
    """Third level - Access Controls, Change Management, etc."""
    
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categories'
    )

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'AC', 'CM'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'categories'
        ordering = ['domain', 'sort_order', 'name']
        verbose_name_plural = 'categories'
        constraints = [
            models.UniqueConstraint(
                fields=['domain', 'code'],
                condition=models.Q(domain__isnull=False),
                name='unique_category_code_per_domain'
            ),
            models.UniqueConstraint(
                fields=['domain', 'name'],
                condition=models.Q(domain__isnull=False),
                name='unique_category_name_per_domain'
            )
        ]

    def __str__(self):
        dom = self.domain
        fw_name = dom.framework.name if dom and dom.framework_id else 'Unlinked'
        return f"{fw_name} - {self.name}"



class Subcategory(BaseModel):
    """Fourth level - User Access Management, System Monitoring, etc."""
    
    category = models.ForeignKey(
    Category,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='subcategories'
    )

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'UAM', 'SAM'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'subcategories'
        ordering = ['category', 'sort_order', 'name']
        verbose_name_plural = 'subcategories'
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'code'],
                condition=models.Q(category__isnull=False),
                name='unique_subcategory_code_per_category'
            ),
            models.UniqueConstraint(
                fields=['category', 'name'],
                condition=models.Q(category__isnull=False),
                name='unique_subcategory_name_per_category'
            )
        ]

    def __str__(self):
        cat = self.category
        dom = cat.domain if cat else None
        fw_name = dom.framework.name if dom and dom.framework_id else 'Unlinked'
        return f"{fw_name} - {self.name}"



class Control(BaseModel):
    """Fifth level - Actual controls like AC-001, CM-001, etc."""
    
    subcategory = models.ForeignKey(
    Subcategory,
    on_delete=models.CASCADE,  # ✅ CORRECT - Keep CASCADE
    null=False,                # ✅ CORRECT - Control MUST have subcategory
    blank=False,               # ✅ CORRECT - Control MUST have subcategory
    related_name='controls'
    )

    control_code = models.CharField(
    max_length=20,
    validators=[
        RegexValidator(
            regex=r'^[A-Z]{2,4}-\d{3}$',
            message='Control code must be like AC-001, CM-001'
        )
    ],
    help_text="Control code like 'AC-001'"
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    objective = models.TextField(
        help_text="What this control aims to achieve"
    )
    control_type = models.CharField(
        max_length=20,
        choices=[
            ('PREVENTIVE', 'Preventive'),
            ('DETECTIVE', 'Detective'),
            ('CORRECTIVE', 'Corrective'),
        ],
        default='PREVENTIVE'
    )
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('CONTINUOUS', 'Continuous'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('ANNUALLY', 'Annually'),
        ],
        default='MONTHLY'
    )
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low'),
        ],
        default='MEDIUM'
    )
    sort_order = models.PositiveIntegerField(default=1)

     # ============ NEW FIELD ADDED ============
    tags = models.ManyToManyField(
        'ControlTag',
        blank=True,
        related_name='controls',
        help_text="Tags for categorization and filtering (cloud, automated, high-priority)"
    )
    
    class Meta:
        db_table = 'controls'
        ordering = ['subcategory', 'sort_order', 'control_code']
        constraints = [
            models.UniqueConstraint(
                fields=['subcategory', 'control_code'],
                condition=models.Q(subcategory__isnull=False),
                name='unique_control_code_per_subcategory'
            )
        ]

        
    def __str__(self):
        return f"{self.control_code} - {self.title}"


class AssessmentQuestion(BaseModel):
    """Questions for each control during assessment"""
    
    control = models.ForeignKey(
        Control, 
        on_delete=models.CASCADE, 
        related_name='assessment_questions'
    )
    question = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[
            ('YES_NO', 'Yes/No'),
            ('MULTIPLE_CHOICE', 'Multiple Choice'),
            ('TEXT', 'Text Response'),
            ('NUMERIC', 'Numeric'),
            ('DATE', 'Date'),
        ],
        default='YES_NO'
    )
    options = models.JSONField(
        blank=True, 
        null=True,
        help_text="For multiple choice questions - list of options"
    )
    is_mandatory = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'assessment_questions'
        ordering = ['control', 'sort_order']
        
    def __str__(self):
        return f"{self.control.control_code} - Q{self.sort_order}"


class EvidenceRequirement(BaseModel):
    """Evidence requirements for each control"""
    
    control = models.ForeignKey(
        Control, 
        on_delete=models.CASCADE, 
        related_name='evidence_requirements'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    evidence_type = models.CharField(
        max_length=20,
        choices=[
            ('DOCUMENT', 'Document'),
            ('SCREENSHOT', 'Screenshot'),
            ('VIDEO', 'Video'),
            ('LOG_FILE', 'Log File'),
            ('REPORT', 'Report'),
            ('POLICY', 'Policy'),
            ('PROCEDURE', 'Procedure'),
        ],
        default='DOCUMENT'
    )
    is_mandatory = models.BooleanField(default=True)
    file_format = models.CharField(
        max_length=50,
        blank=True,
        help_text="Accepted file formats like 'PDF, DOC, XLSX'"
    )
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'evidence_requirements'
        ordering = ['control', 'sort_order']
        
    
    def __str__(self):
        return f"{self.control.control_code} - {self.title}"


# ============================================================================
# NEW MODELS ADDED - Framework Categorization & Metadata
# ============================================================================

class FrameworkCategory(BaseModel):
    """Categorize frameworks by industry/type (Financial, Security, Privacy, etc.)"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name like 'Financial Compliance', 'Information Security'"
    )
    description = models.TextField(blank=True)
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code like 'FIN', 'SEC', 'PRIV'"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name for UI (e.g., 'shield', 'lock', 'document')"
    )
    color = models.CharField(
        max_length=7,
        default='#0066CC',
        help_text="Hex color code for UI"
    )
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'framework_categories'
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Framework Categories'
        
    def __str__(self):
        return self.name


class ControlMapping(BaseModel):
    """Map overlapping/equivalent controls across different frameworks"""
    
    source_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='mappings_as_source',
        help_text="Primary control"
    )
    target_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='mappings_as_target',
        help_text="Related/equivalent control"
    )
    mapping_type = models.CharField(
        max_length=20,
        choices=[
            ('EQUIVALENT', 'Equivalent - Same requirement'),
            ('PARTIAL', 'Partial - Overlapping requirements'),
            ('RELATED', 'Related - Similar concept'),
            ('SUPERSEDES', 'Supersedes - Replaces older control'),
        ],
        default='EQUIVALENT'
    )
    mapping_strength = models.PositiveIntegerField(
        default=100,
        help_text="Strength of mapping (0-100%). 100% = fully equivalent"
    )
    notes = models.TextField(
        blank=True,
        help_text="Explanation of relationship between controls"
    )
    
    class Meta:
        db_table = 'control_mappings'
        unique_together = [['source_control', 'target_control']]
        ordering = ['-mapping_strength', 'source_control']
        
    def __str__(self):
        return f"{self.source_control.control_code} ↔ {self.target_control.control_code} ({self.mapping_strength}%)"


class ControlDependency(BaseModel):
    """Define prerequisite relationships between controls"""
    
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='dependencies',
        help_text="Control that has the dependency"
    )
    depends_on_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='required_by',
        help_text="Control that must be implemented first"
    )
    dependency_type = models.CharField(
        max_length=20,
        choices=[
            ('REQUIRED', 'Required - Must implement first'),
            ('RECOMMENDED', 'Recommended - Should implement first'),
            ('OPTIONAL', 'Optional - Helpful to implement first'),
        ],
        default='REQUIRED'
    )
    description = models.TextField(
        help_text="Why this dependency exists"
    )
    
    class Meta:
        db_table = 'control_dependencies'
        unique_together = [['control', 'depends_on_control']]
        verbose_name_plural = 'Control Dependencies'
        
    def __str__(self):
        return f"{self.control.control_code} depends on {self.depends_on_control.control_code}"


class ControlTag(BaseModel):
    """Tags for categorizing and filtering controls"""
    
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tag name like 'cloud', 'automated', 'high-priority'"
    )
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20,
        choices=[
            ('TECHNICAL', 'Technical'),
            ('OPERATIONAL', 'Operational'),
            ('STRATEGIC', 'Strategic'),
            ('DEPLOYMENT', 'Deployment'),
            ('PRIORITY', 'Priority'),
        ],
        default='TECHNICAL'
    )
    color = models.CharField(
        max_length=7,
        default='#6B7280',
        help_text="Hex color code for UI badge"
    )
    
    class Meta:
        db_table = 'control_tags'
        ordering = ['category', 'name']
        
    def __str__(self):
        return self.name


class ControlReference(BaseModel):
    """External references and documentation links for controls"""
    
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='references'
    )
    reference_type = models.CharField(
        max_length=20,
        choices=[
            ('REGULATION', 'Regulation'),
            ('STANDARD', 'Standard'),
            ('GUIDELINE', 'Guideline'),
            ('BEST_PRACTICE', 'Best Practice'),
            ('DOCUMENTATION', 'Documentation'),
        ],
        default='STANDARD'
    )
    reference_code = models.CharField(
        max_length=100,
        help_text="Reference identifier (e.g., 'SOX Section 404', 'NIST SP 800-53')"
    )
    reference_title = models.CharField(max_length=200)
    reference_url = models.URLField(
        blank=True,
        help_text="Link to external documentation"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'control_references'
        ordering = ['control', 'sort_order']
        
    def __str__(self):
        return f"{self.control.control_code} - {self.reference_code}"


class ImplementationGuidance(BaseModel):
    """Detailed step-by-step implementation guides for controls"""
    
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='implementation_guides'
    )
    title = models.CharField(max_length=200)
    content = models.TextField(
        help_text="Detailed implementation instructions"
    )
    guidance_type = models.CharField(
        max_length=20,
        choices=[
            ('TECHNICAL', 'Technical Implementation'),
            ('PROCEDURAL', 'Procedural Steps'),
            ('POLICY', 'Policy Template'),
            ('EXAMPLE', 'Example/Template'),
        ],
        default='TECHNICAL'
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('BEGINNER', 'Beginner'),
            ('INTERMEDIATE', 'Intermediate'),
            ('ADVANCED', 'Advanced'),
        ],
        default='INTERMEDIATE'
    )
    estimated_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated implementation time in hours"
    )
    prerequisites = models.TextField(
        blank=True,
        help_text="What needs to be in place before starting"
    )
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'implementation_guidance'
        ordering = ['control', 'sort_order']
        verbose_name_plural = 'Implementation Guidance'
        
    def __str__(self):
        return f"{self.control.control_code} - {self.title}"


# ============================================================================
# MANY-TO-MANY RELATIONSHIP TABLE (Add after all models)
# ============================================================================

# Add ManyToMany relationship for Control <-> ControlTag
# This will be added to the Control model (see modification below)
    



    
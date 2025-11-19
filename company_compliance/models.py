"""
Company Compliance Models - Tenant-Specific Data
These models store company-specific framework copies, assignments, assessments, and evidence.
Data resides in tenant schemas/databases.
"""

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
from datetime import date

User = get_user_model()


class BaseModel(models.Model):
    """Abstract base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="User ID who created this (from main DB)"
    )
    updated_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="User ID who last updated this (from main DB)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# ============================================================================
# FRAMEWORK STRUCTURE MODELS (Copies of SuperAdmin Templates)
# ============================================================================

class CompanyFramework(BaseModel):
    """Company's copy of framework template"""
    
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
        ],
        default='ACTIVE'
    )
    
    # Link back to template
    template_framework_id = models.UUIDField(
        help_text="ID of Framework from templates_host (public schema)"
    )
    
    # Customization tracking
    is_customized = models.BooleanField(
        default=False,
        help_text="Has company customized this framework?"
    )
    
    customization_level = models.CharField(
        max_length=20,
        choices=[
            ('VIEW_ONLY', 'View Only - No modifications'),
            ('CONTROL_LEVEL', 'Control Level - Can customize controls'),
            ('FULL', 'Full - Complete independence'),
        ],
        default='CONTROL_LEVEL'
    )
    is_template_synced = models.BooleanField(
        default=True,
        help_text="Is this still synced with template updates?"
    )
    
    # Custom fields (if FULL customization)
    custom_description = models.TextField(
        blank=True,
        help_text="Company-specific description"
    )
    
    # Metadata
    subscribed_at = models.DateTimeField(
        default=timezone.now,
        help_text="When company subscribed to this framework"
    )
    
    class Meta:
        db_table = 'company_frameworks'
        ordering = ['name', 'version']
        
    def __str__(self):
        return f"{self.name} v{self.version}"


class CompanyDomain(BaseModel):
    """Company's copy of domain"""
    
    framework = models.ForeignKey(
        CompanyFramework,
        on_delete=models.CASCADE,
        related_name='domains'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'ITGC', 'BPC'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    # Link back to template
    template_domain_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of Domain from templates_host (if copied from template)"
    )
    
    # Customization
    is_custom = models.BooleanField(
        default=False,
        help_text="Is this a custom domain added by company?"
    )
    
    class Meta:
        db_table = 'company_domains'
        ordering = ['framework', 'sort_order', 'name']
        
    def __str__(self):
        return f"{self.framework.name} - {self.name}"


class CompanyCategory(BaseModel):
    """Company's copy of category"""
    
    domain = models.ForeignKey(
        CompanyDomain,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'AC', 'CM'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    # Link back to template
    template_category_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of Category from templates_host"
    )
    
    # Customization
    is_custom = models.BooleanField(
        default=False,
        help_text="Is this a custom category added by company?"
    )
    
    class Meta:
        db_table = 'company_categories'
        ordering = ['domain', 'sort_order', 'name']
        verbose_name_plural = 'Company Categories'
        
    def __str__(self):
        return f"{self.domain.framework.name} - {self.name}"


class CompanySubcategory(BaseModel):
    """Company's copy of subcategory"""
    
    category = models.ForeignKey(
        CompanyCategory,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10,
        help_text="Short code like 'UAM', 'SAM'"
    )
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    
    # Link back to template
    template_subcategory_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of Subcategory from templates_host"
    )
    
    # Customization
    is_custom = models.BooleanField(
        default=False,
        help_text="Is this a custom subcategory added by company?"
    )
    
    class Meta:
        db_table = 'company_subcategories'
        ordering = ['category', 'sort_order', 'name']
        verbose_name_plural = 'Company Subcategories'
        
    def __str__(self):
        return f"{self.category.domain.framework.name} - {self.name}"


class CompanyControl(BaseModel):
    """Company's copy of control with customization support"""
    
    subcategory = models.ForeignKey(
        CompanySubcategory,
        on_delete=models.CASCADE,
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
    
    # Link back to template
    template_control_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of Control from templates_host"
    )
    
    # ============ CUSTOMIZATION FIELDS ============
    # ============ CUSTOMIZATION FIELDS ============
    is_customized = models.BooleanField(
        default=False,
        help_text="Has company customized this control?"
    )
    can_customize = models.BooleanField(
        default=True,
        help_text="Is company allowed to customize this control?"
    )

    # Custom fields (if customized)
    custom_title = models.CharField(
        max_length=200,
        null=True,  # ✅ ADD THIS
        blank=True,
        help_text="Company's custom title"
    )
    custom_description = models.TextField(
        null=True,  # ✅ ADD THIS
        blank=True,
        help_text="Company's custom description"
    )
    custom_objective = models.TextField(
        null=True,  # ✅ ADD THIS
        blank=True,
        help_text="Company's custom objective"
    )
    custom_procedures = models.TextField(
        null=True,  # ✅ ADD THIS
        blank=True,
        help_text="Company-specific implementation procedures"
    )
        
    # Customization metadata
    customized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When control was customized"
    )
    customized_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="User who customized this control"
    )
    # ==============================================
    
    class Meta:
        db_table = 'company_controls'
        ordering = ['subcategory', 'sort_order', 'control_code']
        indexes = [
            models.Index(fields=['control_code']),
            models.Index(fields=['is_customized']),
        ]
        
    def __str__(self):
        return f"{self.control_code} - {self.title}"
    
    def get_effective_title(self):
        """Return custom title if customized, else original"""
        return self.custom_title if self.is_customized and self.custom_title else self.title
    
    def get_effective_description(self):
        """Return custom description if customized, else original"""
        return self.custom_description if self.is_customized and self.custom_description else self.description


class CompanyAssessmentQuestion(BaseModel):
    """Company's copy of assessment questions"""
    
    control = models.ForeignKey(
        CompanyControl,
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
    
    # Link back to template
    template_question_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of AssessmentQuestion from templates_host"
    )
    
    # Customization
    is_custom = models.BooleanField(
        default=False,
        help_text="Is this a custom question added by company?"
    )
    
    class Meta:
        db_table = 'company_assessment_questions'
        ordering = ['control', 'sort_order']
        
    def __str__(self):
        return f"{self.control.control_code} - Q{self.sort_order}"


class CompanyEvidenceRequirement(BaseModel):
    """Company's copy of evidence requirements"""
    
    control = models.ForeignKey(
        CompanyControl,
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
    
    # Link back to template
    template_evidence_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of EvidenceRequirement from templates_host"
    )
    
    # Customization
    is_custom = models.BooleanField(
        default=False,
        help_text="Is this a custom evidence requirement added by company?"
    )
    
    class Meta:
        db_table = 'company_evidence_requirements'
        ordering = ['control', 'sort_order']
        
    def __str__(self):
        return f"{self.control.control_code} - {self.title}"


# ============================================================================
# OPERATIONAL MODELS (Company-Specific Operations)
# ============================================================================

class ControlAssignment(BaseModel):
    """Assign controls to company employees"""
    
    control = models.ForeignKey(
        CompanyControl,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    # User assignment (user from main DB)
    assigned_to_user_id = models.IntegerField(
        help_text="User ID from main database (auth_user)"
    )
    assigned_to_username = models.CharField(
        max_length=150,
        help_text="Cached username for quick display"
    )
    assigned_to_email = models.EmailField(
        help_text="Cached email for notifications"
    )
    
    assigned_by_user_id = models.IntegerField(
        help_text="User ID who made the assignment"
    )
    
    # Assignment details
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending - Not started'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('OVERDUE', 'Overdue'),
            ('REJECTED', 'Rejected'),
        ],
        default='PENDING'
    )
    priority = models.CharField(
        max_length=20,
        choices=[
            ('HIGH', 'High'),
            ('MEDIUM', 'Medium'),
            ('LOW', 'Low'),
        ],
        default='MEDIUM'
    )
    
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="When control implementation is due"
    )
    completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="When control was completed"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Assignment notes and instructions"
    )
    completion_notes = models.TextField(
        blank=True,
        help_text="Notes added upon completion"
    )
    
    # Notifications
    notification_sent = models.BooleanField(
        default=False,
        help_text="Has assignment notification been sent?"
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Has reminder been sent?"
    )
    
    class Meta:
        db_table = 'control_assignments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['assigned_to_user_id', 'status']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['control']),
        ]
        
    def __str__(self):
        return f"{self.control.control_code} → {self.assigned_to_username}"


class AssessmentCampaign(BaseModel):
    """Assessment/audit cycles (e.g., Q1 2024 SOX Audit)"""
    
    framework = models.ForeignKey(
        CompanyFramework,
        on_delete=models.CASCADE,
        related_name='assessment_campaigns'
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Campaign name like 'Q1 2024 SOX Audit'"
    )
    description = models.TextField(blank=True)
    
    # Timeline
    start_date = models.DateField(
        help_text="Assessment start date"
    )
    end_date = models.DateField(
        help_text="Assessment end date"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('PLANNED', 'Planned'),
            ('IN_PROGRESS', 'In Progress'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='PLANNED'
    )
    
    # Progress tracking
    total_controls = models.IntegerField(
        default=0,
        help_text="Total number of controls in this assessment"
    )
    completed_controls = models.IntegerField(
        default=0,
        help_text="Number of controls assessed"
    )
    completion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Completion percentage (0.00 to 100.00)"
    )
    
    # Compliance scoring
    compliant_count = models.IntegerField(
        default=0,
        help_text="Number of compliant controls"
    )
    non_compliant_count = models.IntegerField(
        default=0,
        help_text="Number of non-compliant controls"
    )
    not_applicable_count = models.IntegerField(
        default=0,
        help_text="Number of N/A controls"
    )
    compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Overall compliance score (0.00 to 100.00)"
    )
    
    # Metadata
    created_by_username = models.CharField(
        max_length=150,
        help_text="Who created this campaign"
    )
    
    class Meta:
        db_table = 'assessment_campaigns'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['framework', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.framework.name})"


class AssessmentResponse(BaseModel):
    """Employee responses to control assessments"""
    
    campaign = models.ForeignKey(
        AssessmentCampaign,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    control = models.ForeignKey(
        CompanyControl,
        on_delete=models.CASCADE,
        related_name='assessment_responses'
    )
    assignment = models.ForeignKey(
        ControlAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessment_responses',
        help_text="Link to assignment if this control was assigned"
    )
    
    # Response
    response = models.CharField(
        max_length=20,
        choices=[
            ('COMPLIANT', 'Compliant'),
            ('NON_COMPLIANT', 'Non-Compliant'),
            ('PARTIAL', 'Partially Compliant'),
            ('NOT_APPLICABLE', 'Not Applicable'),
            ('PENDING', 'Pending Review'),
        ],
        default='PENDING'
    )
    compliance_status = models.CharField(
        max_length=20,
        choices=[
            ('PASS', 'Pass'),
            ('FAIL', 'Fail'),
            ('PARTIAL', 'Partial'),
            ('N/A', 'Not Applicable'),
        ],
        null=True,
        blank=True
    )
    confidence_level = models.CharField(
        max_length=20,
        choices=[
            ('HIGH', 'High Confidence'),
            ('MEDIUM', 'Medium Confidence'),
            ('LOW', 'Low Confidence'),
        ],
        default='MEDIUM'
    )
    
    # Details
    notes = models.TextField(
        blank=True,
        help_text="Assessment notes and findings"
    )
    issues_identified = models.TextField(
        blank=True,
        help_text="Issues or gaps identified"
    )
    remediation_required = models.BooleanField(
        default=False,
        help_text="Does this require remediation?"
    )
    remediation_plan = models.TextField(
        blank=True,
        help_text="Plan to address issues"
    )
    
    # Metadata
    responded_by_user_id = models.IntegerField(
        help_text="User who submitted this response"
    )
    responded_by_username = models.CharField(
        max_length=150,
        help_text="Username for display"
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When response was submitted"
    )
    
    # Review
    reviewed_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="User who reviewed this response"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When response was reviewed"
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Reviewer's notes"
    )
    
    class Meta:
        db_table = 'assessment_responses'
        ordering = ['-responded_at']
        indexes = [
            models.Index(fields=['campaign', 'response']),
            models.Index(fields=['control']),
            models.Index(fields=['responded_by_user_id']),
        ]
        unique_together = [['campaign', 'control']]
        
    def __str__(self):
        return f"{self.campaign.name} - {self.control.control_code} - {self.response}"


class EvidenceDocument(BaseModel):
    """Evidence documents uploaded by users"""
    
    control = models.ForeignKey(
        CompanyControl,
        on_delete=models.CASCADE,
        related_name='evidence_documents'
    )
    response = models.ForeignKey(
        AssessmentResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evidence_documents',
        help_text="Link to assessment response if applicable"
    )
    
    # File details
    file_name = models.CharField(
        max_length=500,
        help_text="Original file name"
    )
    file_path = models.CharField(
        max_length=1000,
        help_text="Path to file in storage (S3, local, etc.)"
    )
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    file_type = models.CharField(
        max_length=100,
        help_text="MIME type (application/pdf, image/png, etc.)"
    )
    file_extension = models.CharField(
        max_length=10,
        help_text="File extension (.pdf, .docx, .xlsx)"
    )
    
    # Metadata
    title = models.CharField(
        max_length=200,
        help_text="Document title/description"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization ['policy', 'screenshot', 'audit-log']"
    )
    
    # Upload info
    uploaded_by_user_id = models.IntegerField(
        help_text="User who uploaded this"
    )
    uploaded_by_username = models.CharField(
        max_length=150,
        help_text="Username for display"
    )
    uploaded_at = models.DateTimeField(
        default=timezone.now,
        help_text="When file was uploaded"
    )
    
    # Status
    is_archived = models.BooleanField(
        default=False,
        help_text="Is this document archived?"
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When document was archived"
    )
    
    # Verification
    is_verified = models.BooleanField(
        default=False,
        help_text="Has this evidence been verified?"
    )
    verified_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="User who verified this"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verified"
    )
    
    class Meta:
        db_table = 'evidence_documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['control']),
            models.Index(fields=['uploaded_by_user_id']),
            models.Index(fields=['is_archived']),
        ]
        
    def __str__(self):
        return f"{self.control.control_code} - {self.file_name}"


class ComplianceReport(BaseModel):
    """Generated compliance reports"""
    
    campaign = models.ForeignKey(
        AssessmentCampaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
        help_text="Associated campaign (if report is for specific campaign)"
    )
    framework = models.ForeignKey(
        CompanyFramework,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="Framework this report covers"
    )
    
    # Report details
    report_type = models.CharField(
        max_length=50,
        choices=[
            ('SUMMARY', 'Summary Report'),
            ('DETAILED', 'Detailed Report'),
            ('EXECUTIVE', 'Executive Summary'),
            ('AUDIT', 'Audit Report'),
            ('GAP_ANALYSIS', 'Gap Analysis'),
        ],
        default='SUMMARY'
    )
    report_format = models.CharField(
        max_length=20,
        choices=[
            ('PDF', 'PDF'),
            ('EXCEL', 'Excel'),
            ('HTML', 'HTML'),
            ('JSON', 'JSON'),
        ],
        default='PDF'
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Report title"
    )
    description = models.TextField(
        blank=True,
        help_text="Report description"
    )
    
    # File
    file_path = models.CharField(
        max_length=1000,
        blank=True,
        help_text="Path to generated report file"
    )
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    
    # Compliance metrics
    overall_compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Overall compliance score (0.00 to 100.00)"
    )
    total_controls = models.IntegerField(
        default=0,
        help_text="Total controls assessed"
    )
    compliant_controls = models.IntegerField(
        default=0,
        help_text="Number of compliant controls"
    )
    non_compliant_controls = models.IntegerField(
        default=0,
        help_text="Number of non-compliant controls"
    )
    not_applicable_controls = models.IntegerField(
        default=0,
        help_text="Number of N/A controls"
    )
    
    # Report metadata
    report_period_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of reporting period"
    )
    report_period_end = models.DateField(
        null=True,
        blank=True,
        help_text="End date of reporting period"
    )
    
    generated_by_user_id = models.IntegerField(
        help_text="User who generated this report"
    )
    generated_by_username = models.CharField(
        max_length=150,
        help_text="Username for display"
    )
    generated_at = models.DateTimeField(
        default=timezone.now,
        help_text="When report was generated"
    )
    
    # Status
    is_final = models.BooleanField(
        default=False,
        help_text="Is this the final version?"
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Has this been published/shared?"
    )
    
    class Meta:
        db_table = 'compliance_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['framework']),
            models.Index(fields=['campaign']),
            models.Index(fields=['generated_at']),
        ]
        
    def __str__(self):
        return f"{self.title} ({self.framework.name})"
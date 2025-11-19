"""
Tenant Management Models - Company/Organization Management
These models handle multi-tenancy, subscriptions, and company provisioning
"""

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.conf import settings
from cryptography.fernet import Fernet
import uuid


class BaseModel(models.Model):
    """Abstract base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class SubscriptionPlan(BaseModel):
    """Subscription tiers (Basic, Professional, Enterprise)"""
    
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Plan code like 'BASIC', 'PROFESSIONAL', 'ENTERPRISE'"
    )
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Pricing
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in USD per month"
    )
    annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in USD per year (discounted)"
    )
    
    # Limits
    max_users = models.IntegerField(
        default=0,
        help_text="Maximum number of users (0 = unlimited)"
    )
    max_frameworks = models.IntegerField(
        default=0,
        help_text="Maximum number of frameworks (0 = unlimited)"
    )
    max_controls = models.IntegerField(
        default=0,
        help_text="Maximum number of controls (0 = unlimited)"
    )
    storage_gb = models.IntegerField(
        default=10,
        help_text="Storage limit in GB"
    )
    
    # Features
    can_create_custom_frameworks = models.BooleanField(
        default=False,
        help_text="Can create custom frameworks from scratch"
    )
    can_customize_controls = models.BooleanField(
        default=True,
        help_text="Can customize individual control descriptions"
    )
    has_api_access = models.BooleanField(
        default=False,
        help_text="Has API access for integrations"
    )
    has_advanced_reporting = models.BooleanField(
        default=False,
        help_text="Advanced compliance reporting features"
    )
    has_sso = models.BooleanField(
        default=False,
        help_text="Single Sign-On (SSO) support"
    )
    
    # Isolation mode
    default_isolation_mode = models.CharField(
        max_length=20,
        choices=[
            ('SCHEMA', 'Schema-based (shared database)'),
            ('DATABASE', 'Database-based (dedicated)'),
        ],
        default='SCHEMA',
        help_text="Default database isolation strategy for this plan"
    )
    
    # Customization level
    default_customization_level = models.CharField(
        max_length=20,
        choices=[
            ('VIEW_ONLY', 'View Only - No customization'),
            ('CONTROL_LEVEL', 'Control Level - Customize controls'),
            ('FULL', 'Full - Complete customization'),
        ],
        default='VIEW_ONLY',
        help_text="Default framework customization level"
    )
    
    # Support
    support_level = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email Support'),
            ('PRIORITY', 'Priority Support'),
            ('DEDICATED', 'Dedicated Account Manager'),
        ],
        default='EMAIL'
    )
    
    sort_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'subscription_plans'
        ordering = ['sort_order', 'monthly_price']
        
    def __str__(self):
        return f"{self.name} (${self.monthly_price}/mo)"


class TenantDatabaseInfo(BaseModel):
    """Tenant/Company database and schema information"""
    
    # Company Info
    tenant_slug = models.SlugField(
        max_length=50,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Slug must be lowercase letters, numbers, and hyphens only'
            )
        ],
        help_text="Unique identifier like 'acmecorp', 'techstartup'"
    )
    company_name = models.CharField(
        max_length=200,
        help_text="Full company name"
    )
    company_email = models.EmailField(
        help_text="Primary contact email"
    )
    company_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
    )
    
    # Database Connection Details
    database_name = models.CharField(
        max_length=100,
        help_text="PostgreSQL database name (if DATABASE mode)"
    )
    database_user = models.CharField(
        max_length=50,
        blank=True,
        help_text="Database user (if DATABASE mode)"
    )
    database_password = models.TextField(
        help_text="Encrypted password (Fernet encryption)"
    )
    database_host = models.CharField(
        max_length=100,
        default='localhost',
        help_text="Database host address"
    )
    database_port = models.CharField(
        max_length=10,
        default='5432',
        help_text="Database port"
    )
    
    # ============ HYBRID APPROACH FIELDS ============
    isolation_mode = models.CharField(
        max_length=20,
        choices=[
            ('DATABASE', 'Separate Database'),
            ('SCHEMA', 'Schema in Shared Database'),
        ],
        default='SCHEMA',
        help_text="Database isolation strategy"
    )
    schema_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Schema name if SCHEMA mode (e.g., 'acmecorp_schema')"
    )
    # ================================================
    
    # Subscription
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='tenants',
        help_text="Current subscription plan"
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('TRIAL', 'Trial Period'),
            ('ACTIVE', 'Active'),
            ('SUSPENDED', 'Suspended'),
            ('CANCELLED', 'Cancelled'),
            ('EXPIRED', 'Expired'),
        ],
        default='TRIAL'
    )
    subscription_start_date = models.DateField(
    null=True,
    blank=True,
    help_text="When subscription started"
    )
    
    subscription_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When subscription ends (null = ongoing)"
    )
    trial_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="When trial period ends"
    )
    
    # Usage Tracking
    current_user_count = models.IntegerField(
        default=0,
        help_text="Current number of active users"
    )
    current_framework_count = models.IntegerField(
        default=0,
        help_text="Current number of subscribed frameworks"
    )
    current_control_count = models.IntegerField(
        default=0,
        help_text="Current number of controls"
    )
    storage_used_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Storage used in GB"
    )
    
    # Provisioning Status
    provisioning_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROVISIONING', 'Provisioning'),
            ('ACTIVE', 'Active'),
            ('FAILED', 'Failed'),
            ('DEPROVISIONING', 'Deprovisioning'),
        ],
        default='PENDING'
    )
    provisioning_error = models.TextField(
        blank=True,
        help_text="Error message if provisioning failed"
    )
    
    # Settings
    user_data_residency = models.CharField(
        max_length=20,
        choices=[
            ('CENTRALIZED', 'Centralized (Main DB)'),
            ('ISOLATED', 'Isolated (Tenant DB)'),
        ],
        default='CENTRALIZED',
        help_text="Where user data is stored"
    )
    
    # Metadata
    provisioned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When provisioning completed"
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time system checked tenant health"
    )
    
    class Meta:
        db_table = 'tenant_database_info'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_slug']),
            models.Index(fields=['provisioning_status']),
            models.Index(fields=['subscription_status']),
        ]
        
    def __str__(self):
        return f"{self.company_name} ({self.tenant_slug})"
    
    def encrypt_password(self, password):
        """Encrypt password using Fernet"""
        fernet = Fernet(settings.DB_ENCRYPTION_KEY.encode())
        encrypted = fernet.encrypt(password.encode())
        self.database_password = encrypted.decode()
    
    def decrypt_password(self):
        """Decrypt password using Fernet"""
        fernet = Fernet(settings.DB_ENCRYPTION_KEY.encode())
        decrypted = fernet.decrypt(self.database_password.encode())
        return decrypted.decode()


class FrameworkSubscription(BaseModel):
    """Track which frameworks each company has subscribed to"""
    
    tenant = models.ForeignKey(
        TenantDatabaseInfo,
        on_delete=models.CASCADE,
        related_name='framework_subscriptions'
    )
    framework_id = models.UUIDField(
        help_text="ID of Framework from templates_host app"
    )
    framework_name = models.CharField(
        max_length=200,
        help_text="Cached framework name for quick access"
    )
    framework_version = models.CharField(
        max_length=20,
        help_text="Version subscribed to (e.g., '1.0')"
    )
    
    # Subscription details
    subscribed_at = models.DateTimeField(
        default=timezone.now,
        help_text="When framework was subscribed"
    )
    subscription_type = models.CharField(
        max_length=20,
        choices=[
            ('INCLUDED', 'Included in plan'),
            ('ADDON', 'Add-on purchase'),
        ],
        default='INCLUDED'
    )
    addon_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price if add-on (monthly)"
    )
    
    # Customization level
    customization_level = models.CharField(
        max_length=20,
        choices=[
            ('VIEW_ONLY', 'View Only - No copy'),
            ('CONTROL_LEVEL', 'Control Level - Full copy, can customize controls'),
            ('FULL', 'Full - Independent copy, full customization'),
        ],
        default='CONTROL_LEVEL',
        help_text="Level of customization allowed"
    )
    
    # Version tracking
    current_version = models.CharField(
        max_length=20,
        help_text="Version currently deployed in tenant schema"
    )
    latest_available_version = models.CharField(
        max_length=20,
        help_text="Latest version available from template"
    )
    upgrade_status = models.CharField(
        max_length=20,
        choices=[
            ('UP_TO_DATE', 'Up to date'),
            ('UPGRADE_AVAILABLE', 'Upgrade available'),
            ('UPGRADE_SCHEDULED', 'Upgrade scheduled'),
            ('UPGRADING', 'Upgrading'),
            ('UPGRADE_FAILED', 'Upgrade failed'),
        ],
        default='UP_TO_DATE'
    )
    last_upgrade_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time system checked for updates"
    )
    scheduled_upgrade_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When upgrade is scheduled"
    )
    
    # Customization tracking
    has_customizations = models.BooleanField(
        default=False,
        help_text="Has tenant customized any controls?"
    )
    customized_controls_count = models.IntegerField(
        default=0,
        help_text="Number of customized controls"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('ACTIVE', 'Active'),
            ('CANCELLED', 'Cancelled'),
            ('SUSPENDED', 'Suspended'),
        ],
        default='ACTIVE'
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When subscription was cancelled"
    )
    
    class Meta:
        db_table = 'framework_subscriptions'
        unique_together = [['tenant', 'framework_id']]
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['upgrade_status']),
        ]
        
    def __str__(self):
        return f"{self.tenant.company_name} - {self.framework_name} v{self.current_version}"


class TenantUsageLog(BaseModel):
    """Track tenant usage metrics over time"""
    
    tenant = models.ForeignKey(
        TenantDatabaseInfo,
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    log_date = models.DateField(
        help_text="Date of this usage snapshot"
    )
    
    # Usage metrics
    user_count = models.IntegerField(
        help_text="Number of active users"
    )
    framework_count = models.IntegerField(
        help_text="Number of subscribed frameworks"
    )
    control_count = models.IntegerField(
        help_text="Total number of controls"
    )
    assessment_count = models.IntegerField(
        default=0,
        help_text="Number of assessment campaigns"
    )
    evidence_count = models.IntegerField(
        default=0,
        help_text="Number of evidence documents"
    )
    storage_used_gb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Storage used in GB"
    )
    
    # API usage (if applicable)
    api_calls_count = models.IntegerField(
        default=0,
        help_text="Number of API calls made"
    )
    
    class Meta:
        db_table = 'tenant_usage_logs'
        unique_together = [['tenant', 'log_date']]
        ordering = ['-log_date']
        indexes = [
            models.Index(fields=['tenant', 'log_date']),
        ]
        
    def __str__(self):
        return f"{self.tenant.company_name} - {self.log_date}"


class TenantBillingHistory(BaseModel):
    """Track billing and payment history"""
    
    tenant = models.ForeignKey(
        TenantDatabaseInfo,
        on_delete=models.CASCADE,
        related_name='billing_history'
    )
    
    billing_period_start = models.DateField(
        help_text="Billing period start date"
    )
    billing_period_end = models.DateField(
        help_text="Billing period end date"
    )
    
    # Charges
    base_plan_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base subscription plan amount"
    )
    addon_frameworks_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Additional framework charges"
    )
    addon_users_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Additional user charges"
    )
    addon_storage_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Additional storage charges"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount for this period"
    )
    
    # Payment
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('FAILED', 'Failed'),
            ('REFUNDED', 'Refunded'),
        ],
        default='PENDING'
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was received"
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment method used (credit card, bank transfer, etc.)"
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Payment gateway transaction ID"
    )
    
    # Invoice
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique invoice number"
    )
    invoice_url = models.URLField(
        blank=True,
        help_text="Link to download invoice PDF"
    )
    
    class Meta:
        db_table = 'tenant_billing_history'
        ordering = ['-billing_period_start']
        indexes = [
            models.Index(fields=['tenant', 'payment_status']),
            models.Index(fields=['billing_period_start']),
            models.Index(fields=['invoice_number']),
        ]
        
    def __str__(self):
        return f"{self.tenant.company_name} - {self.invoice_number}"


class SuperAdminAuditLog(BaseModel):
    """Log all SuperAdmin actions for security and compliance"""
    
    admin_user_id = models.IntegerField(
        help_text="User ID of the admin who performed action"
    )
    admin_username = models.CharField(
        max_length=150,
        help_text="Username for quick reference"
    )
    
    action = models.CharField(
        max_length=50,
        choices=[
            ('VIEW_CREDENTIALS', 'Viewed database credentials'),
            ('IMPERSONATE', 'Impersonated tenant admin'),
            ('QUERY_DATABASE', 'Ran database query'),
            ('CREATE_TENANT', 'Created new tenant'),
            ('DELETE_TENANT', 'Deleted tenant'),
            ('SUSPEND_TENANT', 'Suspended tenant'),
            ('MODIFY_SUBSCRIPTION', 'Modified subscription'),
            ('VIEW_TENANT_DATA', 'Viewed tenant data'),
        ],
        help_text="Action performed by admin"
    )
    
    tenant_slug = models.CharField(
        max_length=50,
        blank=True,
        help_text="Which tenant was affected"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address of admin"
    )
    
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details about the action"
    )
    
    reason = models.TextField(
        blank=True,
        help_text="Reason for performing this action"
    )
    
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When action was performed"
    )
    
    class Meta:
        db_table = 'superadmin_audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['admin_user_id', 'timestamp']),
            models.Index(fields=['tenant_slug', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
        
    def __str__(self):
        return f"{self.admin_username} - {self.action} - {self.timestamp}"
    

# ```

# ---

# ## **BOTTOM LINE - WHAT YOU GOT:** ✅

# ### **5 CORE MODELS:**

# 1. **SubscriptionPlan** - Define Basic/Pro/Enterprise tiers
#    - Pricing (monthly/annual)
#    - Limits (users, frameworks, controls, storage)
#    - Features (custom frameworks, API, SSO)
#    - Default isolation mode (SCHEMA/DATABASE)
#    - Default customization level (VIEW_ONLY/CONTROL_LEVEL/FULL)

# 2. **TenantDatabaseInfo** - Company/tenant provisioning
#    - Company info (slug, name, email, phone)
#    - Database credentials (encrypted password with Fernet)
#    - **HYBRID fields:** `isolation_mode` (SCHEMA/DATABASE), `schema_name`
#    - Subscription tracking (plan, status, dates)
#    - Usage tracking (users, frameworks, controls, storage)
#    - Provisioning status (PENDING/PROVISIONING/ACTIVE/FAILED)
#    - Helper methods: `encrypt_password()`, `decrypt_password()`

# 3. **FrameworkSubscription** - Track framework subscriptions per tenant
#    - Which framework (framework_id, name, version)
#    - Subscription type (INCLUDED/ADDON)
#    - **Customization level:** VIEW_ONLY/CONTROL_LEVEL/FULL
#    - Version tracking (current vs. latest, upgrade status)
#    - Customization tracking (has_customizations, count)
#    - Status (ACTIVE/CANCELLED/SUSPENDED)

# 4. **TenantUsageLog** - Daily usage snapshots
#    - Date-based tracking
#    - Metrics (users, frameworks, controls, assessments, evidence, storage)
#    - API calls count
#    - For analytics and billing

# 5. **TenantBillingHistory** - Invoices and payments
#    - Billing period dates
#    - Charges breakdown (base plan + addons)
#    - Payment tracking (status, method, transaction ID)
#    - Invoice details (number, PDF URL)

# ### **BONUS MODEL:**

# 6. **SuperAdminAuditLog** - Security audit trail
#    - Who (admin user, username, IP)
#    - What (action type)
#    - When (timestamp)
#    - Where (which tenant)
#    - Why (reason)
#    - Details (JSON for extra info)

# ---

# ## **KEY FEATURES:**

# ✅ **Hybrid isolation support** (SCHEMA/DATABASE modes)
# ✅ **Customization levels** (VIEW_ONLY/CONTROL_LEVEL/FULL)
# ✅ **Encrypted passwords** (Fernet encryption methods)
# ✅ **Version tracking** (current vs. latest, upgrade status)
# ✅ **Usage metering** (for billing and limits)
# ✅ **Audit logging** (SuperAdmin actions tracked)
# ✅ **Flexible pricing** (plan limits, addons, features)

# ---

# ## **DATABASE TABLES CREATED:**
# ```
# public schema (main_compliance_system_db):
# ├── subscription_plans
# ├── tenant_database_info ← Core tenant registry
# ├── framework_subscriptions
# ├── tenant_usage_logs
# ├── tenant_billing_history
# └── superadmin_audit_logs
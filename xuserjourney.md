# 🏢 Multi-Tenant Compliance Platform - Complete Architecture

**Version**: 1.0.0  
**Architecture**: Django Monolith with Multi-Tenant Data Isolation  
**Database**: PostgreSQL (Separate Databases/Schemas per Tenant)

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Application Structure](#application-structure)
3. [Data Flow & Architecture](#data-flow--architecture)
4. [Database Architecture](#database-architecture)
5. [Authentication & Authorization](#authentication--authorization)
6. [Multi-Tenancy Implementation](#multi-tenancy-implementation)
7. [Business Logic Flows](#business-logic-flows)
8. [API Endpoints](#api-endpoints)
9. [Permissions Matrix](#permissions-matrix)
10. [Key Features](#key-features)

---

## 🎯 System Overview

### What This Platform Does

This is an **Enterprise Compliance Management System** that helps companies:
- Subscribe to compliance frameworks (SOX, ISO 27001, NIST, etc.)
- Manage controls and evidence
- Run assessment campaigns
- Track compliance scores
- Generate audit reports

### Core Concept: Multi-Tenancy

```
SuperAdmin creates templates → Tenants subscribe → Templates copied to isolated tenant DBs → Tenants customize
```

Each company (tenant) gets:
- ✅ **Isolated database/schema** for their compliance data
- ✅ **Dedicated admin panel** at `/admin/tenant/{tenant_slug}/admin/`
- ✅ **Role-based access control** within their organization
- ✅ **Framework customization** based on subscription plan

---

## 🏗️ Application Structure

### 4 Main Django Apps:

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN DATABASE (default)                   │
├─────────────────────────────────────────────────────────────┤
│  1. templates_host     → Framework templates (SuperAdmin)    │
│  2. tenant_management  → Tenant provisioning & billing       │
│  3. user_management    → Users, roles, memberships           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│             TENANT DATABASES ({tenant_slug}_compliance_db)   │
├─────────────────────────────────────────────────────────────┤
│  4. company_compliance → Frameworks, controls, assessments   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 1. templates_host (Main DB)

**Purpose**: SuperAdmin-managed framework templates that serve as blueprints

### Models Hierarchy:
```
FrameworkCategory (e.g., "Financial Compliance")
    ↓
Framework (e.g., "SOX", "ISO 27001")
    ↓
Domain (e.g., "IT General Controls")
    ↓
Category (e.g., "Access Controls")
    ↓
Subcategory (e.g., "User Access Management")
    ↓
Control (e.g., "AC-001: Password Policy")
    ↓
├── AssessmentQuestion (e.g., "Is MFA enabled?")
    └── EvidenceRequirement (e.g., "Upload access policy PDF")
```

### Key Features:
- **Read-only for tenants** - only SuperAdmin can edit
- **Version control** - track framework versions (e.g., "SOX 2024.1")
- **Distribution system** - copy templates to tenant databases
- **Validation utilities** - ensure framework completeness before distribution

### API Endpoints:
```
GET  /api/v1/templates/frameworks/           # List all frameworks
GET  /api/v1/templates/frameworks/{id}/      # Framework details
POST /api/v1/templates/frameworks/           # Create (SuperAdmin only)
GET  /api/v1/templates/controls/             # List all controls
```

---

## 📦 2. tenant_management (Main DB)

**Purpose**: Tenant provisioning, subscription plans, and billing

### Key Models:

#### SubscriptionPlan
```python
FREE, PROFESSIONAL, ENTERPRISE
- max_users (10, 100, unlimited)
- max_frameworks (1, 10, unlimited)
- max_controls (50, 1000, unlimited)
- isolation_mode (SCHEMA vs DATABASE)
- features: custom_workflows, api_access, sso, etc.
```

#### TenantDatabaseInfo
```python
tenant_slug           # e.g., "acmecorp" (unique identifier)
company_name          # e.g., "AcmeCorp Inc"
subscription_plan     # Link to SubscriptionPlan
subscription_status   # TRIAL, ACTIVE, SUSPENDED, CANCELLED
isolation_mode        # SCHEMA or DATABASE
provisioning_status   # PENDING, PROVISIONING, ACTIVE, FAILED

# Database connection details
database_name         # e.g., "acmecorp_compliance_db"
schema_name          # e.g., "acmecorp_schema" (if using SCHEMA mode)
database_host
database_port
database_password_encrypted

# Usage tracking
current_user_count
current_framework_count
current_control_count
storage_used_gb
```

#### FrameworkSubscription
```python
tenant → framework
customization_level   # VIEW_ONLY, CONTROL_LEVEL, FULL
distributed_at
version_at_subscription
```

### Tenant Lifecycle:

```
1. SuperAdmin creates tenant
   ↓
2. System provisions database/schema
   ↓
3. System creates Django database connection
   ↓
4. Tenant subscribes to frameworks
   ↓
5. Framework data copied to tenant DB
   ↓
6. Users invited → Tenant ready to use
```

### API Endpoints:
```
POST /api/v2/admin/tenants/                    # Create tenant
GET  /api/v2/admin/tenants/                    # List all tenants
GET  /api/v2/admin/tenants/{slug}/             # Tenant details
POST /api/v2/admin/tenants/{slug}/subscribe/   # Subscribe to framework
POST /api/v2/admin/tenants/{slug}/suspend/     # Suspend tenant
GET  /api/v2/admin/tenants/{slug}/usage/       # Usage statistics
```

---

## 📦 3. user_management (Main DB)

**Purpose**: Users, roles, permissions, and tenant memberships

### Key Models:

#### Role
```python
TENANT_ADMIN         # Full access to tenant
COMPLIANCE_MANAGER   # Manage frameworks, campaigns, assign controls
TEAM_LEAD            # Assign controls, review responses
EMPLOYEE             # Submit responses, upload evidence
AUDITOR              # Read-only access to all compliance data
```

#### RolePermission (23 granular permissions)
```python
# Admin Permissions (8)
manage_users, manage_frameworks, manage_settings, 
manage_billing, view_audit_logs, delete_data, 
manage_integrations, manage_workflows

# Control & Campaign Permissions (5)
assign_controls, create_campaigns, review_responses,
customize_controls, manage_evidence

# Employee Permissions (5)
view_assigned_controls, submit_responses, upload_evidence,
view_own_assignments, comment_on_controls

# Auditor Permissions (5)
view_frameworks, view_responses, view_evidence,
view_reports, export_data
```

#### TenantMembership
```python
user → tenant_slug → role
status: PENDING, ACTIVE, SUSPENDED, INACTIVE
invited_by, invited_at, joined_at, last_activity
```

#### TenantInvitation
```python
email → tenant_slug → role
token (UUID for invitation link)
expires_at
status: PENDING, ACCEPTED, EXPIRED, CANCELLED
```

### User Flow:

```
1. User registers → JWT tokens issued
   ↓
2. Admin invites user to tenant
   ↓
3. User receives invitation email with token
   ↓
4. User accepts → TenantMembership created
   ↓
5. User accesses tenant → Middleware validates
   ↓
6. Database routes to correct tenant DB
```

### API Endpoints:
```
POST /api/v2/auth/register/                    # Register user
POST /api/v2/auth/login/                       # Login (JWT tokens)
GET  /api/v2/me/                               # Current user profile
GET  /api/v2/me/memberships/                   # My tenant memberships

GET  /api/v2/tenants/{slug}/members/           # List tenant members
POST /api/v2/tenants/{slug}/invitations/       # Invite user
POST /api/v2/invitations/accept/               # Accept invitation
```

---

## 📦 4. company_compliance (Tenant DB)

**Purpose**: Tenant-specific compliance data (frameworks, controls, assessments)

### Key Models:

#### CompanyFramework
```python
# Copy of Framework template
name, full_name, version, status
template_framework_id         # Link back to template
customization_level           # VIEW_ONLY, CONTROL_LEVEL, FULL
is_customized                 # Has company made changes?
```

#### CompanyControl
```python
# Copy of Control template
control_code, title, description, objective
control_type: PREVENTIVE, DETECTIVE, CORRECTIVE
frequency: CONTINUOUS, DAILY, WEEKLY, MONTHLY, etc.
risk_level: LOW, MEDIUM, HIGH, CRITICAL

# Customization fields
can_customize                 # Based on subscription plan
is_customized
custom_title, custom_description, custom_objective
custom_procedures

# Template link
template_control_id
```

#### ControlAssignment
```python
# Assign controls to users
control → assigned_to_user_id
assigned_by_user_id
status: PENDING, IN_PROGRESS, COMPLETED, OVERDUE
priority: LOW, MEDIUM, HIGH, CRITICAL
due_date
completion_notes
```

#### AssessmentCampaign
```python
# Assessment rounds
name: "Q4 2024 SOX Assessment"
framework, campaign_type: INITIAL, PERIODIC, etc.
start_date, end_date
status: DRAFT, ACTIVE, COMPLETED, CANCELLED
scope: ALL_CONTROLS, SELECTED, RISK_BASED
```

#### AssessmentResponse
```python
# Control assessment results
campaign → control
response: COMPLIANT, NON_COMPLIANT, PARTIAL, NOT_APPLICABLE, PENDING
compliance_status: PASS, FAIL, PARTIAL, N/A
confidence_level: LOW, MEDIUM, HIGH
notes, action_required
responded_by_user_id, responded_at
reviewed_by_user_id, reviewed_at
```

#### EvidenceDocument
```python
# Evidence files
control → file
file_name, file_path, file_size, file_type
title, description, tags
uploaded_by_user_id, uploaded_at
is_verified, verified_by_user_id
```

#### ComplianceReport
```python
# Generated reports
campaign, framework
report_type: SUMMARY, DETAILED, EXECUTIVE, AUDIT, GAP_ANALYSIS
report_format: PDF, EXCEL, HTML, JSON
overall_compliance_score
total_controls, compliant_controls, non_compliant_controls
generated_by_user_id, generated_at
is_final, is_published
```

### API Endpoints:
```
GET  /api/v1/company/frameworks/               # List tenant's frameworks
GET  /api/v1/company/controls/                 # List controls
GET  /api/v1/company/controls/my_assignments/  # My assigned controls
PATCH /api/v1/company/controls/{id}/customize/ # Customize control

GET  /api/v1/company/assignments/              # List assignments
POST /api/v1/company/assignments/              # Create assignment
GET  /api/v1/company/assignments/me/           # My assignments
POST /api/v1/company/assignments/{id}/complete/ # Complete assignment

GET  /api/v1/company/campaigns/                # List campaigns
POST /api/v1/company/campaigns/                # Create campaign
POST /api/v1/company/campaigns/{id}/launch/    # Launch campaign

GET  /api/v1/company/responses/                # List responses
POST /api/v1/company/responses/                # Submit response

GET  /api/v1/company/evidence/                 # List evidence
POST /api/v1/company/evidence/                 # Upload evidence

GET  /api/v1/company/reports/                  # List reports
POST /api/v1/company/reports/                  # Generate report
```

---

## 🔐 Database Architecture

### Multi-Tenant Isolation Strategy

```
┌──────────────────────────────────────────────────────┐
│          PostgreSQL Server (localhost:5432)          │
├──────────────────────────────────────────────────────┤
│                                                       │
│  🗄️  main_compliance_system_db (Main Database)       │
│  ├── templates_host_*                                │
│  ├── tenant_management_*                             │
│  └── user_management_*                               │
│                                                       │
│  🏢 acmecorp_compliance_db (Tenant Database)         │
│  └── company_* (all company_compliance models)       │
│                                                       │
│  🏢 techcorp_compliance_db (Tenant Database)         │
│  └── company_* (all company_compliance models)       │
│                                                       │
│  🏢 financeco_compliance_db (Tenant Database)        │
│  └── company_* (all company_compliance models)       │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### Database Router Logic

```python
class ComplianceRouter:
    def db_for_read(self, model, **hints):
        # System apps → main database
        if model._meta.app_label in ['templates_host', 'tenant_management', 
                                       'user_management', 'auth', ...]:
            return 'default'
        
        # Company compliance → tenant database
        if model._meta.app_label == 'company_compliance':
            tenant = get_current_tenant()  # From middleware
            if tenant:
                return f"{tenant}_compliance_db"
        
        return 'default'
```

### Database Connection Management

When a tenant is created:
1. Physical database created: `CREATE DATABASE acmecorp_compliance_db`
2. Connection added to Django at runtime:
```python
settings.DATABASES[f'{tenant_slug}_compliance_db'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': database_name,
    'USER': database_user,
    'PASSWORD': decrypt(database_password),
    'HOST': database_host,
    'PORT': database_port,
}
```
3. Migrations run: `python manage.py migrate --database={tenant_slug}_compliance_db`

---

## 🔒 Authentication & Authorization

### Authentication Flow

```
1. User Registration/Login
   ↓
2. JWT Tokens Issued (Access + Refresh)
   ↓
3. Client sends: Authorization: Bearer {access_token}
   ↓
4. DRF validates JWT
   ↓
5. Request.user populated
```

### Middleware Chain

```python
1. TenantMiddleware
   - Extracts tenant_slug from:
     • HTTP Header: X-Tenant-Slug
     • Subdomain: acmecorp.platform.com
     • URL Path: /t/acmecorp/...
   - Sets tenant context for database router
   - Validates tenant exists and is ACTIVE

2. TenantAuthorizationMiddleware
   - Verifies user is member of tenant
   - Checks membership status is ACTIVE
   - Attaches membership to request
```

### Permission System (3 Levels)

#### Level 1: API Permission Classes
```python
IsTenantMember          # Must be member of tenant
IsTenantAdmin           # Must be tenant admin
CanAssignControls       # Has 'assign_controls' permission
CanCreateCampaigns      # Has 'create_campaigns' permission
```

#### Level 2: Role-Based Permissions
```python
membership = TenantMembership.objects.get(user=user, tenant_slug=tenant)
has_permission = membership.has_permission('assign_controls')
```

#### Level 3: Object-Level Permissions
```python
# User can only see their own assignments
if not membership.is_admin:
    queryset = queryset.filter(assigned_to_user_id=request.user.id)
```

---

## 🔄 Multi-Tenancy Implementation

### Tenant Context Management

```python
# Thread-safe tenant context storage
_tenant_context: ContextVar[str] = ContextVar('tenant_context', default=None)

def set_current_tenant(tenant_slug):
    _tenant_context.set(tenant_slug)

def get_current_tenant():
    return _tenant_context.get(None)
```

### Request Flow with Tenant Context

```
HTTP Request with X-Tenant-Slug: acmecorp
    ↓
TenantMiddleware
    ├── Extracts tenant_slug = "acmecorp"
    ├── Validates tenant exists and is active
    └── set_current_tenant("acmecorp")
    ↓
TenantAuthorizationMiddleware
    ├── Verifies user is member of acmecorp
    └── Attaches membership to request
    ↓
View Function
    ↓
ORM Query: CompanyFramework.objects.all()
    ↓
Database Router (db_for_read)
    ├── get_current_tenant() → "acmecorp"
    └── Routes to acmecorp_compliance_db
    ↓
PostgreSQL: SELECT * FROM company_frameworks
    ↓
Response
    ↓
Middleware Cleanup
    └── clear_current_tenant()
```

### Tenant Admin Sites (Dynamic Creation)

Each tenant gets a dedicated admin interface:

```
URL: /admin/tenant/acmecorp/admin/

class TenantAdminSite(AdminSite):
    def __init__(self, tenant_slug):
        self.tenant_slug = tenant_slug
    
    def admin_view(self, view):
        def wrapper(request):
            set_current_tenant(self.tenant_slug)
            return view(request)
        return super().admin_view(wrapper)

# Created dynamically at URL resolution time
tenant_admin = create_tenant_admin_site('acmecorp')
```

---

## 📊 Business Logic Flows

### Flow 1: Tenant Provisioning

```
1. SuperAdmin POSTs to /api/v2/admin/tenants/
   {
     "tenant_slug": "acmecorp",
     "company_name": "AcmeCorp Inc",
     "subscription_plan_code": "PROFESSIONAL"
   }
   ↓
2. Validator checks:
   - tenant_slug is valid (lowercase, alphanumeric, hyphens)
   - tenant_slug not reserved
   - tenant_slug unique
   ↓
3. provision_tenant() utility:
   - Creates PostgreSQL database
   - Generates database credentials
   - Creates TenantDatabaseInfo record
   ↓
4. add_tenant_database_to_django():
   - Adds database connection to settings.DATABASES
   - Runs migrations on new database
   ↓
5. Return:
   {
     "success": true,
     "tenant_slug": "acmecorp",
     "database_name": "acmecorp_compliance_db",
     "provisioning_status": "ACTIVE"
   }
```

### Flow 2: Framework Subscription & Distribution

```
1. SuperAdmin POSTs to /api/v2/admin/tenants/acmecorp/subscribe/
   {
     "framework_id": "uuid-of-SOX-framework",
     "customization_level": "CONTROL_LEVEL"
   }
   ↓
2. copy_framework_to_tenant():
   - Sets tenant context
   - Fetches Framework from templates_host (main DB)
   - Creates CompanyFramework in tenant DB
   ↓
3. For each Domain in Framework:
   - Create CompanyDomain (with template_domain_id link)
   ↓
4. For each Category in Domain:
   - Create CompanyCategory (with template_category_id link)
   ↓
5. For each Subcategory in Category:
   - Create CompanySubcategory (with template_subcategory_id link)
   ↓
6. For each Control in Subcategory:
   - Create CompanyControl (with template_control_id link)
   - Copy AssessmentQuestions
   - Copy EvidenceRequirements
   ↓
7. Create FrameworkSubscription record:
   {
     "tenant": tenant,
     "framework_id": framework_id,
     "framework_name": "SOX",
     "customization_level": "CONTROL_LEVEL",
     "distributed_at": now()
   }
   ↓
8. Increment usage counters:
   - tenant.current_framework_count += 1
   - tenant.current_control_count += control_count
```

### Flow 3: Control Assignment

```
1. Manager POSTs to /api/v1/company/assignments/
   {
     "control_id": "uuid-of-AC-001",
     "assigned_to_user_id": 123,
     "priority": "HIGH",
     "due_date": "2024-12-31"
   }
   ↓
2. Permission check: CanAssignControls
   ↓
3. Validate:
   - Control exists in tenant database
   - User is member of tenant
   - Due date is future
   ↓
4. Create ControlAssignment:
   {
     "control": control,
     "assigned_to_user_id": 123,
     "assigned_by_user_id": request.user.id,
     "status": "PENDING",
     "priority": "HIGH"
   }
   ↓
5. (Optional) Send notification to assigned user
   ↓
6. Return assignment details
```

### Flow 4: Assessment Campaign

```
1. Admin POSTs to /api/v1/company/campaigns/
   {
     "name": "Q4 2024 SOX Assessment",
     "framework_id": "uuid",
     "start_date": "2024-10-01",
     "end_date": "2024-12-31",
     "scope": "ALL_CONTROLS"
   }
   ↓
2. Permission check: CanCreateCampaigns
   ↓
3. Create AssessmentCampaign (status: DRAFT)
   ↓
4. Admin POSTs to /campaigns/{id}/launch/
   ↓
5. System:
   - Sets status to ACTIVE
   - Creates placeholder AssessmentResponse for each control
   - (Optional) Sends notifications to assigned users
   ↓
6. Campaign is live, users can submit responses
```

### Flow 5: Response Submission

```
1. Employee POSTs to /api/v1/company/responses/
   {
     "campaign_id": "uuid",
     "control_id": "uuid",
     "response": "COMPLIANT",
     "compliance_status": "PASS",
     "confidence_level": "HIGH",
     "notes": "MFA is enabled for all users"
   }
   ↓
2. Permission check: CanSubmitResponses
   ↓
3. Validate:
   - User is assigned to control OR is admin
   - Campaign is ACTIVE
   - Response hasn't been submitted yet
   ↓
4. Create/Update AssessmentResponse:
   {
     "campaign": campaign,
     "control": control,
     "response": "COMPLIANT",
     "responded_by_user_id": user.id,
     "responded_at": now()
   }
   ↓
5. (Optional) Mark ControlAssignment as COMPLETED
   ↓
6. Return response details
```

### Flow 6: Evidence Upload

```
1. User POSTs multipart/form-data to /api/v1/company/evidence/
   {
     "control_id": "uuid",
     "file": File,
     "title": "Password Policy Document",
     "description": "Company password requirements"
   }
   ↓
2. Permission check: CanUploadEvidence
   ↓
3. Validate:
   - File type allowed (PDF, DOCX, XLSX, PNG, JPG)
   - File size < limit (e.g., 50MB)
   - User assigned to control OR is admin
   ↓
4. Store file:
   - Upload to storage (S3, local media/)
   - Generate file_path
   ↓
5. Create EvidenceDocument:
   {
     "control": control,
     "file_name": "password_policy.pdf",
     "file_path": "s3://bucket/tenant/evidence/...",
     "file_size": 124567,
     "file_type": "application/pdf",
     "uploaded_by_user_id": user.id
   }
   ↓
6. Return evidence details with download link
```

### Flow 7: Report Generation

```
1. Manager POSTs to /api/v1/company/reports/
   {
     "campaign_id": "uuid",
     "framework_id": "uuid",
     "report_type": "EXECUTIVE",
     "report_format": "PDF"
   }
   ↓
2. Permission check: CanViewReports
   ↓
3. Calculate metrics:
   - Fetch all responses for campaign
   - Count: compliant, non_compliant, partial, n/a
   - Calculate: overall_compliance_score
   ↓
4. Generate report file (PDF/Excel/HTML):
   - Use reporting library (ReportLab, openpyxl)
   - Include: framework info, compliance scores, charts
   ↓
5. Store report file
   ↓
6. Create ComplianceReport record:
   {
     "campaign": campaign,
     "framework": framework,
     "overall_compliance_score": 87.5,
     "total_controls": 120,
     "compliant_controls": 105,
     "file_path": "s3://bucket/reports/..."
   }
   ↓
7. Return report details with download link
```

---

## 🔑 Permissions Matrix

### Role Permissions Breakdown

| Permission | TENANT_ADMIN | COMPLIANCE_MANAGER | TEAM_LEAD | EMPLOYEE | AUDITOR |
|------------|--------------|-------------------|-----------|----------|---------|
| **Admin Permissions** |
| manage_users | ✅ | ❌ | ❌ | ❌ | ❌ |
| manage_frameworks | ✅ | ✅ | ❌ | ❌ | ❌ |
| manage_settings | ✅ | ❌ | ❌ | ❌ | ❌ |
| manage_billing | ✅ | ❌ | ❌ | ❌ | ❌ |
| view_audit_logs | ✅ | ✅ | ❌ | ❌ | ✅ |
| delete_data | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Control Permissions** |
| assign_controls | ✅ | ✅ | ✅ | ❌ | ❌ |
| create_campaigns | ✅ | ✅ | ❌ | ❌ | ❌ |
| review_responses | ✅ | ✅ | ✅ | ❌ | ❌ |
| customize_controls | ✅ | ✅ | ❌ | ❌ | ❌ |
| manage_evidence | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Employee Permissions** |
| view_assigned_controls | ✅ | ✅ | ✅ | ✅ | ❌ |
| submit_responses | ✅ | ✅ | ✅ | ✅ | ❌ |
| upload_evidence | ✅ | ✅ | ✅ | ✅ | ❌ |
| view_own_assignments | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Auditor Permissions** |
| view_frameworks | ✅ | ✅ | ✅ | ❌ | ✅ |
| view_responses | ✅ | ✅ | ✅ | ❌ | ✅ |
| view_evidence | ✅ | ✅ | ✅ | ❌ | ✅ |
| view_reports | ✅ | ✅ | ✅ | ❌ | ✅ |
| export_data | ✅ | ✅ | ❌ | ❌ | ✅ |

---

## ✨ Key Features

### 1. Template Distribution System
- SuperAdmin creates framework templates
- Tenants subscribe to frameworks
- System copies framework hierarchy to tenant database
- Maintains link to original template via `template_*_id` fields
- Allows customization based on subscription plan

### 2. Dynamic Admin Sites
- Each tenant gets isolated admin panel
- URL: `/admin/tenant/{tenant_slug}/admin/`
- Automatically routes queries to correct database
- Shows tenant-specific statistics on dashboard

### 3. Granular RBAC
- 5 predefined roles with 23 permissions
- Permission checks at API level
- Role-based filtering of querysets
- Object-level permissions (e.g., user can only see own assignments)

### 4. Control Assignment System
- Managers assign controls to team members
- Priorities: LOW, MEDIUM, HIGH, CRITICAL
- Due date tracking
- Status tracking: PENDING → IN_PROGRESS → COMPLETED
- Email notifications (optional)

### 5. Assessment Campaigns
- Run periodic assessments
- Track compliance over time
- Bulk response submission
- Campaign status: DRAFT → ACTIVE → COMPLETED

### 6. Evidence Management
- Upload multiple file types
- Link evidence to controls
- Verification workflow
- Archiving support
- Download evidence files

### 7. Compliance Reporting
- Multiple report types: SUMMARY, DETAILED, EXECUTIVE, AUDIT, GAP_ANALYSIS
- Multiple formats: PDF, Excel, HTML, JSON
- Automatic calculation of compliance scores
- Historical tracking

### 8. Framework Customization
- View Only: No changes allowed
- Control Level: Customize control descriptions, procedures
- Full: Complete independence from template

### 9. Usage Tracking
- Monitor users, frameworks, controls per tenant
- Storage usage tracking
- Enforce plan limits
- Billing history

### 10. Tenant Isolation
- Complete data separation
- Separate databases per tenant
- Tenant context validation on every request
- Cannot access other tenant's data

---

## 🚀 Complete User Journey

### Scenario: AcmeCorp Implements SOX Compliance

#### Step 1: Tenant Provisioning (SuperAdmin)
```bash
POST /api/v2/admin/tenants/
{
  "tenant_slug": "acmecorp",
  "company_name": "AcmeCorp Inc",
  "company_email": "admin@acmecorp.com",
  "subscription_plan_code": "PROFESSIONAL"
}
→ Creates acmecorp_compliance_db database
→ Status: ACTIVE
```

#### Step 2: Framework Subscription (SuperAdmin)
```bash
POST /api/v2/admin/tenants/acmecorp/subscribe/
{
  "framework_id": "uuid-of-SOX",
  "customization_level": "CONTROL_LEVEL"
}
→ Copies 150 SOX controls to acmecorp_compliance_db
→ Creates FrameworkSubscription record
```

#### Step 3: User Invitation (Tenant Admin)
```bash
POST /api/v2/tenants/acmecorp/invitations/
{
  "email": "john@acmecorp.com",
  "role_code": "COMPLIANCE_MANAGER"
}
→ Sends invitation email with token
→ John accepts → TenantMembership created
```

#### Step 4: Control Assignment (Compliance Manager)
```bash
POST /api/v1/company/assignments/
{
  "control_id": "uuid-of-AC-001-Password-Policy",
  "assigned_to_user_id": 456,  # Sarah, IT Admin
  "priority": "HIGH",
  "due_date": "2024-12-15"
}
→ Sarah receives notification
→ Assignment appears in her dashboard
```

#### Step 5: Assessment Campaign (Compliance Manager)
```bash
POST /api/v1/company/campaigns/
{
  "name": "Q4 2024 SOX Assessment",
  "framework_id": "uuid-of-SOX",
  "start_date": "2024-10-01",
  "end_date": "2024-12-31"
}

POST /api/v1/company/campaigns/{id}/launch/
→ Campaign goes ACTIVE
→ All assigned users notified
```

#### Step 6: Response Submission (Employee - Sarah)
```bash
POST /api/v1/company/responses/
{
  "campaign_id": "uuid",
  "control_id": "uuid-of-AC-001",
  "response": "COMPLIANT",
  "compliance_status": "PASS",
  "confidence_level": "HIGH",
  "notes": "MFA enabled for all users. Last audit: Oct 1."
}
→ Response recorded
→ Assignment marked COMPLETED
```

#### Step 7: Evidence Upload (Employee - Sarah)
```bash
POST /api/v1/company/evidence/
{
  "control_id": "uuid-of-AC-001",
  "file": password_policy.pdf,
  "title": "Password Policy v2.1"
}
→ File uploaded to S3
→ Evidence linked to control
```

#### Step 8: Report Generation (Compliance Manager)
```bash
POST /api/v1/company/reports/
{
  "campaign_id": "uuid",
  "report_type": "EXECUTIVE",
  "report_format": "PDF"
}
→ System calculates: 87.5% compliance (105/120 controls)
→ Generates PDF report with charts
→ Report available for download
```

---

## 📌 Critical Implementation Details

### Tenant Context is Everything
```python
# EVERY request to company_compliance endpoints needs:
Headers: {
  "Authorization": "Bearer {jwt_token}",
  "X-Tenant-Slug": "acmecorp"
}

# Middleware extracts tenant_slug → validates → sets context
# Database router uses context to route queries
```

### Database Router Behavior
```python
# When you write:
CompanyFramework.objects.all()

# Django checks:
1. What's the app_label? → 'company_compliance'
2. Call router.db_for_read()
3. Router gets tenant from context: 'acmecorp'
4. Returns database: 'acmecorp_compliance_db'
5. Query runs on that database

# NO tenant context? → Falls back to 'default' → NO DATA FOUND
```

### User IDs Stored as Integers
```python
# company_compliance models store user references as integers
# WHY? Cross-database foreign keys not supported
created_by_user_id = models.IntegerField()
assigned_to_user_id = models.IntegerField()

# To get user details, query main database:
from django.contrib.auth.models import User
user = User.objects.using('default').get(id=user_id)
```

### Migrations Per Database
```bash
# Main database
python manage.py migrate

# Tenant databases (one at a time)
python manage.py migrate --database=acmecorp_compliance_db
python manage.py migrate --database=techcorp_compliance_db

# Run after adding new tenant OR changing company_compliance models
```

### Exempt Paths (No Tenant Required)
```python
# These paths don't need tenant context:
/admin/                  # Main Django admin
/api/v2/admin/          # SuperAdmin tenant management
/api/v2/auth/           # Authentication
/api/v1/templates/      # Template management

# These REQUIRE tenant context:
/api/v1/company/*       # All company_compliance endpoints
```

---

## 🎯 Summary

This is a **production-grade multi-tenant SaaS platform** with:

✅ **Complete data isolation** - Each tenant has separate database  
✅ **Flexible RBAC** - 5 roles, 23 permissions  
✅ **Framework distribution** - Templates → Tenant copies  
✅ **Dynamic admin sites** - Per-tenant admin panels  
✅ **Full compliance workflow** - Assign → Assess → Evidence → Report  
✅ **Tenant middleware** - Automatic context management  
✅ **Database routing** - Transparent multi-DB support  
✅ **Subscription plans** - FREE, PROFESSIONAL, ENTERPRISE  
✅ **Usage tracking** - Monitor limits and billing  
✅ **JWT authentication** - Secure API access  

**Next Steps**:
- Add async task processing (Celery) for report generation
- Implement email notifications (invitation, assignment, due dates)
- Add file storage service (S3 integration)
- Build frontend (React/Vue) consuming these APIs
- Add WebSocket support for real-time updates
- Implement audit logging for compliance tracking

---

**Documentation Version**: 1.0.0  
**Last Updated**: November 2024  
**Maintained By**: Your Development Team


INPUT:
{
  "tenant_slug": "acmecorp",
  "company_name": "AcmeCorp Inc",
  "company_email": "admin@acmecorp.com",
  "subscription_plan_code": "PROFESSIONAL"
}

WHAT HAPPENS:
1. ✅ Creates record in tenant_database_info table (public schema)
2. ✅ Creates PostgreSQL schema: acmecorp_schema
3. ✅ Runs migrations → Creates 12 empty tables in acmecorp_schema:
   - company_frameworks
   - company_domains
   - company_categories
   - company_subcategories
   - company_controls
   - company_assessment_questions
   - company_evidence_requirements
   - control_assignments
   - assessment_campaigns
   - assessment_responses
   - evidence_documents
   - compliance_reports
4. ✅ Sets subscription_status = 'TRIAL' ← YOU WANT TO CHANGE THIS
5. ✅ Sets trial_end_date = today + 30 days ← YOU WANT TO REMOVE THIS

RESULT:
- Company entry created ✅
- Empty schema with tables ✅
- NO frameworks yet ❌
- NO users created ❌ (users are separate)
- subscription_status = 'TRIAL' ← Problem!




def provision_tenant(tenant_slug, company_name, subscription_plan_code='BASIC'):
    """
    Complete tenant provisioning - MONOLITH VERSION
    Creates database/schema, runs migrations, ready for frameworks
    """
    logger.info(f"\n[PROVISIONING] Provisioning tenant: {company_name} ({tenant_slug})")
    
    steps = {
        'credentials': None,
        'tenant_record': None,
        'isolation_decision': None,
        'postgres_provision': None,
        'django_connection': None,
        'migrations': None,
        'final_status': None,
    }
    
    try:
        # 1) Get subscription plan
        from .models import SubscriptionPlan
        subscription_plan = SubscriptionPlan.objects.get(code=subscription_plan_code)
        
        # 2) SCHEMA mode (always)
        isolation_mode = 'SCHEMA'
        steps['isolation_decision'] = {'mode': isolation_mode, 'plan': subscription_plan_code}
        logger.info(f"[INFO] Using SCHEMA isolation mode")
        
        # 3) Set schema credentials (uses main database)
        db_name = 'main_compliance_system_db'
        db_user = settings.DATABASES['default']['USER']
        db_password = settings.DATABASES['default']['PASSWORD']
        schema_name = f"{tenant_slug}_schema"

        
        steps['credentials'] = {
            'db_name': db_name,
            'schema_name': schema_name,
            'mode': isolation_mode
        }
        
        # 4) Create tenant record
        tenant_info = TenantDatabaseInfo.objects.create(
            tenant_slug=tenant_slug,
            company_name=company_name,
            database_name=db_name,
            database_user=db_user,
            database_host=settings.DATABASES['default']['HOST'],
            database_port=settings.DATABASES['default']['PORT'],
            subscription_plan=subscription_plan,
            provisioning_status='PROVISIONING',
            schema_name=schema_name,
            is_active=True,\
            subscription_start_date=timezone.now().date(),  # ✅ ADD THIS
            trial_end_date=timezone.now().date() + timedelta(days=30),  # ✅ ADD THIS (30-day trial)
        )
        tenant_info.encrypt_password(db_password)
        tenant_info.save()
        steps['tenant_record'] = {'id': str(tenant_info.id)}
        logger.info(f"[SUCCESS] Created tenant record: {tenant_info.id}")
        
        
        create_postgresql_schema(schema_name)
        steps['postgres_provision'] = {'type': 'schema', 'name': schema_name}


        # 6) Register Django connection
        connection_name = add_tenant_database_to_django(tenant_info)
        steps['django_connection'] = {'connection_name': connection_name}
        
        # 7) Run migrations
        migration_result = run_tenant_migrations(tenant_slug, connection_name)
        steps['migrations'] = migration_result
        
        # 7b) If migrations failed, force create tables
        if not migration_result['success']:
            logger.warning(f"[WARN] Migrations failed, forcing table creation...")
            force_result = force_create_company_tables(
                connection_name=connection_name,
                schema_name=tenant_info.schema_name
            )
            steps['force_tables'] = force_result
            
            # Update migration result if force creation succeeded
            if force_result['success']:
                migration_result = force_result
                logger.info(f"[SUCCESS] Tables created via force method")

        # 8) Update status
        if migration_result['success']:
            tenant_info.provisioning_status = 'ACTIVE'
            tenant_info.subscription_status = 'TRIAL'  # Start with trial
            logger.info(f"[SUCCESS] Tenant {tenant_slug} provisioned successfully!")
        else:
            tenant_info.provisioning_status = 'FAILED'
            logger.error(f"[ERROR] Tenant {tenant_slug} provisioning failed")
        
        tenant_info.save()
        steps['final_status'] = tenant_info.provisioning_status
        
        return {
            'success': migration_result['success'],
            'tenant_info': tenant_info,
            'connection_name': connection_name,
            'steps': steps
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Provisioning error: {e}")
        if 'tenant_info' in locals():
            tenant_info.provisioning_status = 'FAILED'
            tenant_info.save()
        raise


# 🎉 **Success! Here are ALL Tenant Management Endpoints**

---

## 📋 **TENANT MANAGEMENT API ENDPOINTS**

### **Base URL:** `/api/v2/admin/`

---

## 1️⃣ **SUBSCRIPTION PLANS** (Read-Only for Most Users)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/plans/` | List all subscription plans | All SuperAdmins |
| GET | `/plans/{id}/` | Get plan details | All SuperAdmins |
| POST | `/plans/` | Create new plan | SuperAdmin Only |
| PUT/PATCH | `/plans/{id}/` | Update plan | SuperAdmin Only |

---

## 2️⃣ **TENANT CRUD OPERATIONS**

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| **GET** | `/tenants/` | List all tenants | Tenant list with filters |
| **GET** | `/tenants/{slug}/` | Get tenant details | Full tenant info |
| **POST** | `/tenants/` | Create new tenant | PENDING_PAYMENT status |
| **PATCH** | `/tenants/{slug}/` | Update tenant info | Updated tenant |
| **DELETE** | `/tenants/{slug}/` | Soft delete tenant | Marks as inactive |

---

## 3️⃣ **TENANT ACTIVATION & PAYMENT FLOW** ⭐

| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| **POST** | `/tenants/{slug}/activate/` | Activate tenant after payment | After payment confirmed |
| **DELETE** | `/tenants/{slug}/delete_pending/` | Delete pending tenant | If payment fails |

**Activate Request Body:**
```json
{
  "framework_id": "uuid-of-framework",
  "customization_level": "CONTROL_LEVEL",  // Optional
  "payment_id": "pay_xxxxx"  // Optional reference
}
```

---

## 4️⃣ **TENANT FRAMEWORK MANAGEMENT**

| Method | Endpoint | Description | When to Use |
|--------|----------|-------------|-------------|
| **POST** | `/tenants/{slug}/subscribe/` | Subscribe to additional framework | After tenant is ACTIVE |
| **GET** | `/tenants/{slug}/frameworks/` | List tenant's frameworks | Anytime |

**Subscribe Request Body:**
```json
{
  "framework_id": "uuid-of-framework",
  "customization_level": "CONTROL_LEVEL"  // Optional
}
```

---

## 5️⃣ **TENANT STATUS MANAGEMENT**

| Method | Endpoint | Description | Effect |
|--------|----------|-------------|--------|
| **POST** | `/tenants/{slug}/suspend/` | Suspend tenant | Status → SUSPENDED |
| **POST** | `/tenants/{slug}/activate/` | Reactivate suspended tenant | Status → ACTIVE |

---

## 6️⃣ **TENANT USAGE & MONITORING**

| Method | Endpoint | Description | Returns |
|--------|----------|-------------|---------|
| **GET** | `/tenants/{slug}/usage/` | Get usage statistics | Users, frameworks, storage stats |

**Response:**
```json
{
  "tenant_slug": "luck",
  "current_usage": {
    "users": 5,
    "frameworks": 2,
    "controls": 150,
    "storage_gb": 2.5
  },
  "plan_limits": {
    "max_users": 50,
    "max_frameworks": 5,
    "storage_gb": 50
  },
  "usage_history": [...]
}
```

---

## 7️⃣ **FRAMEWORK SUBSCRIPTIONS** (Read-Only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/framework-subscriptions/` | List all subscriptions |
| GET | `/framework-subscriptions/{id}/` | Get subscription details |

**Filter by:** `tenant__tenant_slug`, `status`, `customization_level`

---

## 📊 **QUERY PARAMETERS (Filters)**

### **GET /tenants/** supports:

| Parameter | Example | Description |
|-----------|---------|-------------|
| `subscription_status` | `?subscription_status=ACTIVE` | Filter by status |
| `provisioning_status` | `?provisioning_status=ACTIVE` | Filter by provisioning |
| `is_active` | `?is_active=true` | Active tenants only |
| `show_deleted` | `?show_deleted=true` | Include deleted tenants |
| `search` | `?search=acme` | Search by slug, name, email |
| `ordering` | `?ordering=-created_at` | Sort results |

---

## 🔐 **AUTHENTICATION**

All endpoints require:
```http
Authorization: Bearer <your-superadmin-jwt-token>
```

---

## 🎯 **COMPLETE TENANT LIFECYCLE**

### **1. Create Tenant (PENDING_PAYMENT)**
```bash
POST /api/v2/admin/tenants/
{
  "tenant_slug": "newcorp",
  "company_name": "New Corp",
  "company_email": "admin@newcorp.com",
  "subscription_plan_code": "PROFESSIONAL"
}

Response: {
  "status": "PENDING_PAYMENT",
  "payment_required": true,
  "amount": 599.00
}
```

### **2. Activate Tenant (After Payment)**
```bash
POST /api/v2/admin/tenants/newcorp/activate/
{
  "framework_id": "uuid-of-sox",
  "payment_id": "pay_12345"
}

Response: {
  "status": "ACTIVE",
  "framework_subscribed": true
}
```

### **3. Subscribe to Additional Framework**
```bash
POST /api/v2/admin/tenants/newcorp/subscribe/
{
  "framework_id": "uuid-of-iso27001"
}

Response: {
  "success": true,
  "message": "Subscribed to ISO 27001"
}
```

### **4. Monitor Usage**
```bash
GET /api/v2/admin/tenants/newcorp/usage/

Response: {
  "current_usage": { ... },
  "plan_limits": { ... }
}
```

### **5. Suspend (if needed)**
```bash
POST /api/v2/admin/tenants/newcorp/suspend/

Response: {
  "success": true,
  "message": "Tenant suspended"
}
```

---

## 📝 **STATUS FLOW DIAGRAM**

```
PENDING_PAYMENT (record only, no schema)
    ↓
    POST /activate/
    ↓
ACTIVE (schema created, framework copied)
    ↓
    ├─→ POST /subscribe/ → Add more frameworks
    ├─→ POST /suspend/ → SUSPENDED
    ├─→ DELETE → CANCELLED
    └─→ GET /usage/ → Monitor usage
```

---

## ✅ **QUICK REFERENCE CARD**

| Task | Method | Endpoint |
|------|--------|----------|
| **List plans** | GET | `/plans/` |
| **List tenants** | GET | `/tenants/` |
| **Create tenant** | POST | `/tenants/` |
| **Activate tenant** | POST | `/tenants/{slug}/activate/` |
| **Delete pending** | DELETE | `/tenants/{slug}/delete_pending/` |
| **Add framework** | POST | `/tenants/{slug}/subscribe/` |
| **View frameworks** | GET | `/tenants/{slug}/frameworks/` |
| **Suspend** | POST | `/tenants/{slug}/suspend/` |
| **Check usage** | GET | `/tenants/{slug}/usage/` |
| **Update info** | PATCH | `/tenants/{slug}/` |

---

## 🎉 **You Now Have:**

✅ Tenant creation flow  
✅ Payment-first activation  
✅ Framework distribution  
✅ Status management  
✅ Usage monitoring  
✅ Multi-framework support  

**All working!** 🚀

Need anything else?


Step 3: Test API Endpoints with Postman/curl
Test 1: Submit Assignment for Review
bashPOST http://localhost:8000/api/v1/company/assignments/{assignment_id}/submit_for_review/
Headers:
  Authorization: Bearer <token>
  X-Tenant-Slug: luck
Expected Response:
json{
  "success": true,
  "message": "Assignment submitted for review",
  "assignment": {
    "id": "...",
    "status": "COMPLETED",
    "review_status": "PENDING_REVIEW"
  }
}

Test 2: Get Pending Reviews (Manager/Admin)
bashGET http://localhost:8000/api/v1/company/assignments/pending_review/
Headers:
  Authorization: Bearer <manager-token>
  X-Tenant-Slug: luck
Expected Response:
json{
  "total": 1,
  "assignments": [
    {
      "id": "...",
      "control": {...},
      "assigned_to_username": "john",
      "status": "COMPLETED",
      "review_status": "PENDING_REVIEW",
      "submitted_for_review_at": "2025-11-19T10:30:00Z"
    }
  ]
}

Test 3: Approve Assignment
bashPOST http://localhost:8000/api/v1/company/assignments/{assignment_id}/approve/
Headers:
  Authorization: Bearer <manager-token>
  X-Tenant-Slug: luck
Body:
{
  "notes": "Approved. Good work implementing the control."
}
Expected Response:
json{
  "success": true,
  "message": "Assignment approved successfully",
  "assignment": {
    "id": "...",
    "status": "COMPLETED",
    "review_status": "APPROVED",
    "approved_by_username": "manager",
    "approved_at": "2025-11-19T10:35:00Z",
    "approval_notes": "Approved. Good work implementing the control."
  }
}

Test 4: Reject Assignment
bashPOST http://localhost:8000/api/v1/company/assignments/{assignment_id}/reject/
Headers:
  Authorization: Bearer <manager-token>
  X-Tenant-Slug: luck
Body:
{
  "reason": "Missing evidence document. Please upload the policy document."
}
Expected Response:
json{
  "success": true,
  "message": "Assignment rejected. User will be notified to make revisions.",
  "assignment": {
    "id": "...",
    "status": "REJECTED",
    "review_status": "REJECTED",
    "rejected_by_username": "manager",
    "rejected_at": "2025-11-19T10:40:00Z",
    "rejection_reason": "Missing evidence document. Please upload the policy document.",
    "revision_count": 1
  }
}

Test 5: Test Separation of Duties (Should Fail)
bash# Employee tries to approve their own assignment
POST http://localhost:8000/api/v1/company/assignments/{assignment_id}/approve/
Headers:
  Authorization: Bearer <employee-token>  # Same user who submitted
  X-Tenant-Slug: luck
Expected Response (403 Forbidden):
json{
  "success": false,
  "error": "Cannot approve your own assignment (separation of duties)"
}

Test 6: Test Without Permission (Should Fail)
bash# Employee tries to approve (no permission)
POST http://localhost:8000/api/v1/company/assignments/{assignment_id}/approve/
Headers:
  Authorization: Bearer <employee-token>
  X-Tenant-Slug: luck
Expected Response (403 Forbidden):
json{
  "detail": "You do not have permission to perform this action."
}
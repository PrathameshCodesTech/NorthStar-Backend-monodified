# user_management/permission_registry.py

SUPPORTED_PERMISSIONS = [
    # ============================================================================
    # TENANT ADMIN PERMISSIONS
    # ============================================================================
    ('manage_users', 'Manage Users'),
    ('manage_frameworks', 'Manage Frameworks'),
    ('manage_settings', 'Manage Settings'),
    ('manage_billing', 'Manage Billing'),
    ('view_audit_logs', 'View Audit Logs'),
    
    # ============================================================================
    # CONTROL & CAMPAIGN PERMISSIONS
    # ============================================================================
    ('assign_controls', 'Assign Controls'),
    ('create_campaigns', 'Create Campaigns'),
    
    # ============================================================================
    # COMPLIANCE MANAGER PERMISSIONS
    # ============================================================================
    ('review_responses', 'Review Responses'),
    ('manage_evidence', 'Manage Evidence'),
    ('customize_controls', 'Customize Controls'),
    
    # ============================================================================
    # EMPLOYEE PERMISSIONS
    # ============================================================================
    ('view_assigned_controls', 'View Assigned Controls'),
    ('submit_responses', 'Submit Assessment Responses'),
    ('upload_evidence', 'Upload Evidence Documents'),
    ('view_own_assignments', 'View Own Assignments'),
    
    # ============================================================================
    # AUDITOR PERMISSIONS
    # ============================================================================
    ('view_frameworks', 'View Frameworks'),
    ('view_responses', 'View Responses'),
    ('view_evidence', 'View Evidence'),
    ('view_reports', 'View Compliance Reports'),
    ('export_data', 'Export Data'),
    ('generate_reports', 'Generate Compliance Reports'),
    
    # ============================================================================
    # ⭐ NEW: APPROVAL WORKFLOW PERMISSIONS
    # ============================================================================
    ('approve_assignments', 'Approve Control Assignments'),
    ('reject_assignments', 'Reject Control Assignments'),
    ('approve_responses', 'Approve Assessment Responses'),
    ('reject_responses', 'Reject Assessment Responses'),
    ('verify_evidence', 'Verify Evidence Documents'),
    ('reject_evidence', 'Reject Evidence Documents'),
]
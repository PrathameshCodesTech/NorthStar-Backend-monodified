"""
Approval Workflow Business Logic
Centralized logic for approval/rejection decisions across all approval types
"""

from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONTROL ASSIGNMENT APPROVAL LOGIC
# ============================================================================

def can_approve_assignment(user, membership, assignment):
    """
    Check if user can approve a control assignment
    
    Args:
        user: User object
        membership: TenantMembership object (from request.tenant_membership)
        assignment: ControlAssignment object
    
    Returns:
        tuple: (can_approve: bool, reason: str)
    """
    # Check 1: Must have approval permission
    if not membership.has_permission('approve_assignments'):
        return False, "You don't have permission to approve assignments"
    
    # Check 2: Cannot approve own work (separation of duties)
    if assignment.assigned_to_user_id == user.id:
        return False, "Cannot approve your own assignment (separation of duties)"
    
    # Check 3: Assignment must be in correct status
    valid_statuses = ['COMPLETED', 'PENDING_REVIEW', 'UNDER_REVIEW']
    if assignment.status not in valid_statuses:
        return False, f"Cannot approve assignment in '{assignment.status}' status. Must be COMPLETED, PENDING_REVIEW, or UNDER_REVIEW."
    
    # Check 4: Review status must be appropriate
    if assignment.review_status == 'APPROVED':
        return False, "Assignment is already approved"
    
    # Check 5: Role hierarchy (optional but recommended)
    # Manager or Compliance Officer or Admin can approve
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER', 'MANAGER']
    if membership.role.code not in allowed_roles:
        return False, f"Only Managers and Compliance Officers can approve assignments. Your role: {membership.role.name}"
    
    return True, "Can approve"


def can_reject_assignment(user, membership, assignment):
    """
    Check if user can reject a control assignment
    Same rules as approval
    
    Args:
        user: User object
        membership: TenantMembership object
        assignment: ControlAssignment object
    
    Returns:
        tuple: (can_reject: bool, reason: str)
    """
    # Same permission checks as approve
    if not membership.has_permission('reject_assignments'):
        # Fall back to approve_assignments permission (same privilege)
        if not membership.has_permission('approve_assignments'):
            return False, "You don't have permission to reject assignments"
    
    # Cannot reject own work
    if assignment.assigned_to_user_id == user.id:
        return False, "Cannot reject your own assignment (separation of duties)"
    
    # Must be in reviewable status
    valid_statuses = ['COMPLETED', 'PENDING_REVIEW', 'UNDER_REVIEW']
    if assignment.status not in valid_statuses:
        return False, f"Cannot reject assignment in '{assignment.status}' status"
    
    # Check review status
    if assignment.review_status == 'APPROVED':
        return False, "Cannot reject an already approved assignment"
    
    # Role check
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER', 'MANAGER']
    if membership.role.code not in allowed_roles:
        return False, f"Only Managers and Compliance Officers can reject assignments"
    
    return True, "Can reject"


def approve_assignment(assignment, approver_user, notes=''):
    """
    Approve an assignment (updates status)
    
    Args:
        assignment: ControlAssignment object
        approver_user: User object
        notes: Optional approval notes
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Update status
        assignment.status = 'COMPLETED'  # Keep original status as COMPLETED
        assignment.review_status = 'APPROVED'
        
        # Set approver info
        assignment.approved_by_user_id = approver_user.id
        assignment.approved_by_username = approver_user.username
        assignment.approved_at = timezone.now()
        assignment.approval_notes = notes
        
        assignment.save()
        
        logger.info(
            f"[APPROVAL] Assignment {assignment.id} approved by {approver_user.username}"
        )
        
        return True, "Assignment approved successfully"
        
    except Exception as e:
        logger.error(f"[APPROVAL ERROR] Failed to approve assignment: {e}")
        return False, f"Failed to approve: {str(e)}"


def reject_assignment(assignment, rejector_user, reason):
    """
    Reject an assignment (sends back for revision)
    
    Args:
        assignment: ControlAssignment object
        rejector_user: User object
        reason: Rejection reason (required)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not reason or not reason.strip():
        return False, "Rejection reason is required"
    
    try:
        # Update status
        assignment.status = 'REJECTED'
        assignment.review_status = 'REJECTED'
        
        # Set rejector info
        assignment.rejected_by_user_id = rejector_user.id
        assignment.rejected_by_username = rejector_user.username
        assignment.rejected_at = timezone.now()
        assignment.rejection_reason = reason
        
        # Increment revision count
        assignment.revision_count += 1
        
        assignment.save()
        
        logger.info(
            f"[REJECTION] Assignment {assignment.id} rejected by {rejector_user.username}. "
            f"Reason: {reason[:100]}"
        )
        
        return True, "Assignment rejected. User will be notified to make revisions."
        
    except Exception as e:
        logger.error(f"[REJECTION ERROR] Failed to reject assignment: {e}")
        return False, f"Failed to reject: {str(e)}"


# ============================================================================
# ASSESSMENT RESPONSE APPROVAL LOGIC
# ============================================================================

def can_approve_response(user, membership, response):
    """
    Check if user can approve an assessment response
    
    Args:
        user: User object
        membership: TenantMembership object
        response: AssessmentResponse object
    
    Returns:
        tuple: (can_approve: bool, reason: str)
    """
    # Check 1: Must have approval permission
    if not membership.has_permission('approve_responses'):
        return False, "You don't have permission to approve responses"
    
    # Check 2: Cannot approve own response
    if response.responded_by_user_id == user.id:
        return False, "Cannot approve your own response (separation of duties)"
    
    # Check 3: Response must be submitted
    valid_review_statuses = ['SUBMITTED', 'UNDER_REVIEW']
    if response.review_status not in valid_review_statuses:
        return False, f"Response must be submitted for review. Current status: {response.review_status}"
    
    # Check 4: Already approved check
    if response.review_status == 'APPROVED':
        return False, "Response is already approved"
    
    # Check 5: Role check - Only Compliance Officers and Admins
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER']
    if membership.role.code not in allowed_roles:
        return False, f"Only Compliance Officers can approve responses. Your role: {membership.role.name}"
    
    return True, "Can approve"


def can_reject_response(user, membership, response):
    """Check if user can reject an assessment response"""
    # Same permission checks as approve
    if not membership.has_permission('reject_responses'):
        if not membership.has_permission('approve_responses'):
            return False, "You don't have permission to reject responses"
    
    # Cannot reject own response
    if response.responded_by_user_id == user.id:
        return False, "Cannot reject your own response (separation of duties)"
    
    # Must be in reviewable status
    valid_review_statuses = ['SUBMITTED', 'UNDER_REVIEW']
    if response.review_status not in valid_review_statuses:
        return False, f"Response must be submitted for review"
    
    # Already approved check
    if response.review_status == 'APPROVED':
        return False, "Cannot reject an already approved response"
    
    # Role check
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER']
    if membership.role.code not in allowed_roles:
        return False, "Only Compliance Officers can reject responses"
    
    return True, "Can reject"


def approve_response(response, approver_user, notes=''):
    """Approve an assessment response"""
    try:
        response.review_status = 'APPROVED'
        response.compliance_status = 'PASS'  # Mark as passed
        
        response.approved_by_user_id = approver_user.id
        response.approved_by_username = approver_user.username
        response.approved_at = timezone.now()
        response.approval_notes = notes
        
        # Also set reviewed fields
        response.reviewed_by_user_id = approver_user.id
        response.reviewed_at = timezone.now()
        response.review_notes = notes
        
        response.save()
        
        logger.info(
            f"[APPROVAL] Response {response.id} approved by {approver_user.username}"
        )
        
        return True, "Response approved successfully"
        
    except Exception as e:
        logger.error(f"[APPROVAL ERROR] Failed to approve response: {e}")
        return False, f"Failed to approve: {str(e)}"


def reject_response(response, rejector_user, reason):
    """Reject an assessment response"""
    if not reason or not reason.strip():
        return False, "Rejection reason is required"
    
    try:
        response.review_status = 'REJECTED'
        response.compliance_status = 'FAIL'  # Mark as failed
        
        response.rejected_by_user_id = rejector_user.id
        response.rejected_by_username = rejector_user.username
        response.rejected_at = timezone.now()
        response.rejection_reason = reason
        
        # Increment revision count
        response.revision_count += 1
        
        # Also set reviewed fields
        response.reviewed_by_user_id = rejector_user.id
        response.reviewed_at = timezone.now()
        response.review_notes = f"REJECTED: {reason}"
        
        response.save()
        
        logger.info(
            f"[REJECTION] Response {response.id} rejected by {rejector_user.username}"
        )
        
        return True, "Response rejected. User will be notified to revise."
        
    except Exception as e:
        logger.error(f"[REJECTION ERROR] Failed to reject response: {e}")
        return False, f"Failed to reject: {str(e)}"


# ============================================================================
# EVIDENCE DOCUMENT VERIFICATION LOGIC
# ============================================================================

def can_verify_evidence(user, membership, evidence):
    """
    Check if user can verify evidence document
    
    Args:
        user: User object
        membership: TenantMembership object
        evidence: EvidenceDocument object
    
    Returns:
        tuple: (can_verify: bool, reason: str)
    """
    # Check 1: Must have verification permission
    if not membership.has_permission('verify_evidence'):
        return False, "You don't have permission to verify evidence"
    
    # Check 2: Cannot verify own upload
    if evidence.uploaded_by_user_id == user.id:
        return False, "Cannot verify your own evidence (separation of duties)"
    
    # Check 3: Must be in verifiable status
    valid_statuses = ['PENDING', 'SUBMITTED', 'UNDER_VERIFICATION']
    if evidence.verification_status not in valid_statuses:
        return False, f"Evidence must be pending verification. Current status: {evidence.verification_status}"
    
    # Check 4: Already verified check
    if evidence.verification_status == 'VERIFIED':
        return False, "Evidence is already verified"
    
    # Check 5: Role check
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER']
    if membership.role.code not in allowed_roles:
        return False, "Only Compliance Officers can verify evidence"
    
    return True, "Can verify"


def can_reject_evidence(user, membership, evidence):
    """Check if user can reject evidence"""
    # Same permission checks as verify
    if not membership.has_permission('reject_evidence'):
        if not membership.has_permission('verify_evidence'):
            return False, "You don't have permission to reject evidence"
    
    # Cannot reject own upload
    if evidence.uploaded_by_user_id == user.id:
        return False, "Cannot reject your own evidence (separation of duties)"
    
    # Must be in verifiable status
    valid_statuses = ['PENDING', 'SUBMITTED', 'UNDER_VERIFICATION']
    if evidence.verification_status not in valid_statuses:
        return False, "Evidence must be pending verification"
    
    # Already verified check
    if evidence.verification_status == 'VERIFIED':
        return False, "Cannot reject already verified evidence"
    
    # Role check
    allowed_roles = ['TENANT_ADMIN', 'COMPLIANCE_MANAGER']
    if membership.role.code not in allowed_roles:
        return False, "Only Compliance Officers can reject evidence"
    
    return True, "Can reject"


def verify_evidence(evidence, verifier_user, notes=''):
    """Verify an evidence document"""
    try:
        evidence.verification_status = 'VERIFIED'
        evidence.is_verified = True
        
        evidence.verified_by_user_id = verifier_user.id
        evidence.verified_at = timezone.now()
        
        evidence.save()
        
        logger.info(
            f"[VERIFICATION] Evidence {evidence.id} verified by {verifier_user.username}"
        )
        
        return True, "Evidence verified successfully"
        
    except Exception as e:
        logger.error(f"[VERIFICATION ERROR] Failed to verify evidence: {e}")
        return False, f"Failed to verify: {str(e)}"


def reject_evidence(evidence, rejector_user, reason):
    """Reject an evidence document"""
    if not reason or not reason.strip():
        return False, "Rejection reason is required"
    
    try:
        # Save current version to history
        if evidence.file_path:
            previous_version = {
                'file_name': evidence.file_name,
                'file_path': evidence.file_path,
                'rejected_at': timezone.now().isoformat(),
                'rejected_by': rejector_user.username,
                'reason': reason
            }
            evidence.previous_versions.append(previous_version)
        
        evidence.verification_status = 'REJECTED'
        evidence.is_verified = False
        
        evidence.rejected_by_user_id = rejector_user.id
        evidence.rejected_by_username = rejector_user.username
        evidence.rejected_at = timezone.now()
        evidence.rejection_reason = reason
        
        # Increment resubmission count
        evidence.resubmission_count += 1
        
        evidence.save()
        
        logger.info(
            f"[REJECTION] Evidence {evidence.id} rejected by {rejector_user.username}"
        )
        
        return True, "Evidence rejected. User will be notified to upload corrected version."
        
    except Exception as e:
        logger.error(f"[REJECTION ERROR] Failed to reject evidence: {e}")
        return False, f"Failed to reject: {str(e)}"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_approval_history(obj):
    """
    Get approval history for any object (assignment, response, evidence)
    
    Returns:
        list: History of approval/rejection events
    """
    history = []
    
    # Check if approved
    if hasattr(obj, 'approved_at') and obj.approved_at:
        history.append({
            'action': 'APPROVED',
            'by': obj.approved_by_username if hasattr(obj, 'approved_by_username') else 'Unknown',
            'at': obj.approved_at,
            'notes': getattr(obj, 'approval_notes', '')
        })
    
    # Check if rejected
    if hasattr(obj, 'rejected_at') and obj.rejected_at:
        history.append({
            'action': 'REJECTED',
            'by': obj.rejected_by_username if hasattr(obj, 'rejected_by_username') else 'Unknown',
            'at': obj.rejected_at,
            'reason': getattr(obj, 'rejection_reason', '')
        })
    
    # Sort by timestamp
    history.sort(key=lambda x: x['at'], reverse=True)
    
    return history
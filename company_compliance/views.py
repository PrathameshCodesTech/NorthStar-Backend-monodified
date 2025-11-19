"""
Company Compliance API Views
Tenant-specific compliance operations
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal


from .models import (
    CompanyFramework, CompanyControl, ControlAssignment,
    AssessmentCampaign, AssessmentResponse, EvidenceDocument,
    ComplianceReport
)
from .serializers import (
    CompanyFrameworkListSerializer, CompanyFrameworkDetailSerializer,
    CompanyControlListSerializer, CompanyControlDetailSerializer,
    CompanyControlCustomizeSerializer,
    ControlAssignmentListSerializer, ControlAssignmentDetailSerializer,
    ControlAssignmentCreateSerializer, ControlAssignmentUpdateSerializer,
    AssessmentCampaignListSerializer, AssessmentCampaignDetailSerializer,
    AssessmentCampaignCreateSerializer,
    AssessmentResponseListSerializer, AssessmentResponseDetailSerializer,
    AssessmentResponseCreateSerializer,
    EvidenceDocumentSerializer, EvidenceDocumentUploadSerializer,
    ComplianceReportSerializer
)
from .permissions import (
    IsTenantMember,
    IsTenantAdmin,
    CanManageUsers,
    CanManageFrameworks,
    CanManageSettings,
    CanAssignControls,
    CanCreateCampaigns,
    CanReviewResponses,
    CanManageEvidence,
    CanCustomizeControls,
    CanViewAssignedControls,
    CanSubmitResponses,
    CanUploadEvidence,
    CanViewOwnAssignments,
    CanViewFrameworks,
    CanViewResponses,
    CanViewEvidence,
    CanViewReports,
    CanExportData,
    CanManageBilling,
    CanViewAuditLogs,
)

# Import plan-based permissions from tenant_management
from tenant_management.permissions import (
    CanCustomizeControls as PlanCanCustomizeControls,
    CanCreateCustomFrameworks as PlanCanCreateCustomFrameworks,
    HasAPIAccess,
)


# ============================================================================
# FRAMEWORK VIEWS
# ============================================================================

class CompanyFrameworkViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Company frameworks (tenant-specific)
    
    GET /api/v1/company/frameworks/
    GET /api/v1/company/frameworks/{id}/
    
    Note: Creating/editing frameworks requires Enterprise plan
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember, PlanCanCreateCustomFrameworks]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'customization_level']
    search_fields = ['name', 'full_name', 'description']
    ordering_fields = ['name', 'subscribed_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Filter by tenant (set by middleware/context)"""
        return CompanyFramework.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyFrameworkListSerializer
        return CompanyFrameworkDetailSerializer


# ============================================================================
# CONTROL VIEWS
# ============================================================================

class CompanyControlViewSet(viewsets.ModelViewSet):
    """
    Company controls (tenant-specific)
    
    GET /api/v1/company/controls/
    GET /api/v1/company/controls/{id}/
    PATCH /api/v1/company/controls/{id}/customize/
    
    Note: Customizing controls requires Professional or Enterprise plan
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember, PlanCanCustomizeControls]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['control_type', 'frequency', 'risk_level', 'is_customized']
    search_fields = ['control_code', 'title', 'custom_title', 'description']
    ordering_fields = ['control_code', 'risk_level']
    ordering = ['control_code']
    
    def get_queryset(self):
        """Optimize queries"""
        return CompanyControl.objects.filter(
            is_active=True
        ).select_related(
            'subcategory',
            'subcategory__category',
            'subcategory__category__domain',
            'subcategory__category__domain__framework'
        ).prefetch_related(
            'assessment_questions',
            'evidence_requirements',
            'assignments'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyControlListSerializer
        elif self.action == 'customize':
            return CompanyControlCustomizeSerializer
        return CompanyControlDetailSerializer
    
    
    @action(detail=True, methods=['patch'])
    def customize(self, request, pk=None):
        """
        Customize control
        
        PATCH /api/v1/company/controls/{id}/customize/
        {
            "custom_title": "Enhanced Password Policy",
            "custom_description": "Our specific requirements...",
            "custom_procedures": "1. Step one..."
        }
        
        Plan-based restrictions:
        - BASIC: Cannot customize at all (403)
        - PROFESSIONAL: Can customize title, description, objective, procedures
        - ENTERPRISE: Can customize everything + add/remove controls
        """
        control = self.get_object()
        
        # ============ ENFORCE PLAN-BASED CUSTOMIZATION ============
        from core.database_router import get_current_tenant
        from tenant_management.models import TenantDatabaseInfo
        import logging
        
        logger = logging.getLogger(__name__)
        tenant_slug = get_current_tenant()
        
        try:
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            plan = tenant.subscription_plan
            
            # Check basic permission (BASIC plan blocked by permission class, but double-check)
            if not plan.can_customize_controls:
                return Response({
                    'success': False,
                    'error': 'Control customization requires Professional or Enterprise plan',
                    'upgrade_required': True,
                    'current_plan': plan.code,
                    'upgrade_to': 'PROFESSIONAL'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if trying to modify control structure (ENTERPRISE only)
            restricted_fields = ['control_id', 'control_code', 'framework', 'domain', 'category', 'subcategory']
            attempting_restricted = [field for field in restricted_fields if field in request.data]
            
            if attempting_restricted:
                if not plan.can_create_custom_frameworks:
                    return Response({
                        'success': False,
                        'error': 'Modifying control structure requires Enterprise plan',
                        'upgrade_required': True,
                        'current_plan': plan.code,
                        'upgrade_to': 'ENTERPRISE',
                        'restricted_fields': attempting_restricted,
                        'message': 'You can only modify control descriptions with Professional plan'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # PROFESSIONAL: Only allow specific fields
            allowed_fields_professional = [
                'custom_title', 'custom_description', 
                'custom_objective', 'custom_procedures',
                'custom_implementation_guidance'
            ]
            
            # ENTERPRISE: Can modify all fields (no restriction)
            if plan.code == 'PROFESSIONAL':
                # Validate only allowed fields are being modified
                disallowed = [k for k in request.data.keys() if k not in allowed_fields_professional]
                if disallowed:
                    return Response({
                        'success': False,
                        'error': f'Fields {disallowed} require Enterprise plan to modify',
                        'upgrade_required': True,
                        'current_plan': plan.code,
                        'upgrade_to': 'ENTERPRISE',
                        'allowed_fields': allowed_fields_professional,
                        'restricted_fields': disallowed
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Log customization attempt for audit
            logger.info(
                f"[CONTROL CUSTOMIZATION] Tenant: {tenant_slug}, "
                f"Plan: {plan.code}, Control: {control.control_code}, "
                f"User: {request.user.username}, "
                f"Fields: {list(request.data.keys())}"
            )
            
        except TenantDatabaseInfo.DoesNotExist:
            logger.error(f"[CONTROL CUSTOMIZATION] Tenant not found: {tenant_slug}")
            return Response({
                'success': False,
                'error': 'Tenant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        # ==========================================================
        
        # Check control-level flag
        if not control.can_customize:
            return Response({
                'success': False,
                'error': 'This control does not allow customization',
                'message': 'Control customization is disabled for this specific control'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Proceed with customization
        serializer = self.get_serializer(control, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Control customized successfully',
            'plan': plan.code,
            'control': CompanyControlDetailSerializer(control).data
        })
    
    @action(detail=False, methods=['get'])
    def my_assignments(self, request):
        """
        Get controls assigned to current user
        
        GET /api/v1/company/controls/my_assignments/
        """
        assignments = ControlAssignment.objects.filter(
            assigned_to_user_id=request.user.id,
            is_active=True,
            status__in=['PENDING', 'IN_PROGRESS']
        ).select_related('control')
        
        controls = [assignment.control for assignment in assignments]
        serializer = CompanyControlListSerializer(controls, many=True)
        
        return Response({
            'count': len(controls),
            'controls': serializer.data
        })


# ============================================================================
# ASSIGNMENT VIEWS
# ============================================================================

class ControlAssignmentViewSet(viewsets.ModelViewSet):
    """
    Control assignments
    
    GET /api/v1/company/assignments/
    POST /api/v1/company/assignments/
    GET /api/v1/company/assignments/me/
    PATCH /api/v1/company/assignments/{id}/
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'assigned_to_user_id']
    search_fields = ['control__control_code', 'control__title', 'assigned_to_username']
    ordering_fields = ['due_date', 'created_at', 'priority']
    ordering = ['due_date']
    
    def get_queryset(self):
        """Filter assignments"""
        queryset = ControlAssignment.objects.filter(
            is_active=True
        ).select_related('control')
        
        # Filter by user if not admin
        if not self.request.user.is_superuser:
            from user_management.models import TenantMembership
            
            tenant_slug = getattr(self.request, 'tenant_slug', None)
            
            try:
                membership = TenantMembership.objects.get(
                    user=self.request.user,
                    tenant_slug=tenant_slug,
                    is_active=True
                )
                
                # If not admin/manager, only show own assignments
                if not (membership.is_admin or membership.can_assign_controls):
                    queryset = queryset.filter(assigned_to_user_id=self.request.user.id)
                    
            except TenantMembership.DoesNotExist:
                return ControlAssignment.objects.none()
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ControlAssignmentListSerializer
        elif self.action == 'create':
            return ControlAssignmentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ControlAssignmentUpdateSerializer
        return ControlAssignmentDetailSerializer
    
    def get_permissions(self):
        """Different permissions for different actions"""
        if self.action == 'create':
            return [IsAuthenticated(), CanAssignControls()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user's assignments
        
        GET /api/v1/company/assignments/me/
        """
        assignments = ControlAssignment.objects.filter(
            assigned_to_user_id=request.user.id,
            is_active=True
        ).select_related('control').order_by('due_date')
        
        serializer = ControlAssignmentListSerializer(assignments, many=True)
        
        # Group by status
        pending = [a for a in serializer.data if a['status'] == 'PENDING']
        in_progress = [a for a in serializer.data if a['status'] == 'IN_PROGRESS']
        completed = [a for a in serializer.data if a['status'] == 'COMPLETED']
        
        return Response({
            'total': len(serializer.data),
            'by_status': {
                'pending': len(pending),
                'in_progress': len(in_progress),
                'completed': len(completed)
            },
            'assignments': {
                'pending': pending,
                'in_progress': in_progress,
                'completed': completed
            }
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark assignment as complete
        
        POST /api/v1/company/assignments/{id}/complete/
        {
            "completion_notes": "All requirements met"
        }
        """
        assignment = self.get_object()
        
        # Verify user is assigned or is admin
        if assignment.assigned_to_user_id != request.user.id:
            if not request.user.is_superuser:
                from user_management.models import TenantMembership
                
                tenant_slug = getattr(request, 'tenant_slug', None)
                membership = TenantMembership.objects.filter(
                    user=request.user,
                    tenant_slug=tenant_slug,
                    is_active=True
                ).first()
                
                if not membership or not membership.is_admin:
                    return Response({
                        'error': 'You can only complete your own assignments'
                    }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ControlAssignmentUpdateSerializer(
            assignment,
            data={
                'status': 'COMPLETED',
                'completion_notes': request.data.get('completion_notes', '')
            },
            partial=True
        )
        
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Assignment marked as complete',
            'assignment': ControlAssignmentDetailSerializer(assignment).data
        })
    

# ... (Part 1 continues here) ...


# ============================================================================
# CAMPAIGN VIEWS
# ============================================================================

class AssessmentCampaignViewSet(viewsets.ModelViewSet):
    """
    Assessment campaigns
    
    GET /api/v1/company/campaigns/
    POST /api/v1/company/campaigns/
    GET /api/v1/company/campaigns/{id}/
    PATCH /api/v1/company/campaigns/{id}/
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['framework', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['start_date', 'created_at', 'compliance_score']
    ordering = ['-start_date']
    
    def get_queryset(self):
        """Filter campaigns"""
        return AssessmentCampaign.objects.filter(
            is_active=True
        ).select_related('framework')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AssessmentCampaignListSerializer
        elif self.action == 'create':
            return AssessmentCampaignCreateSerializer
        return AssessmentCampaignDetailSerializer
    
    def get_permissions(self):
        """Require campaign management permission for create/update"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanCreateCampaigns()]
        return super().get_permissions()
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Start campaign
        
        POST /api/v1/company/campaigns/{id}/start/
        """
        campaign = self.get_object()
        
        if campaign.status != 'PLANNED':
            return Response({
                'error': f'Campaign is already {campaign.status.lower()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        campaign.status = 'IN_PROGRESS'
        campaign.save()
        
        return Response({
            'success': True,
            'message': 'Campaign started',
            'campaign': AssessmentCampaignDetailSerializer(campaign).data
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete campaign
        
        POST /api/v1/company/campaigns/{id}/complete/
        """
        campaign = self.get_object()
        
        if campaign.status == 'COMPLETED':
            return Response({
                'error': 'Campaign is already completed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        campaign.status = 'COMPLETED'
        campaign.save()
        
        return Response({
            'success': True,
            'message': 'Campaign completed',
            'campaign': AssessmentCampaignDetailSerializer(campaign).data
        })
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """
        Get campaign progress details
        
        GET /api/v1/company/campaigns/{id}/progress/
        """
        campaign = self.get_object()
        
        responses = AssessmentResponse.objects.filter(
            campaign=campaign,
            is_active=True
        )
        
        # Group by compliance status
        by_status = {
            'compliant': responses.filter(compliance_status='COMPLIANT').count(),
            'non_compliant': responses.filter(compliance_status='NON_COMPLIANT').count(),
            'partial': responses.filter(compliance_status='PARTIAL').count(),
            'not_applicable': responses.filter(compliance_status='NOT_APPLICABLE').count()
        }
        
        # Group by control type
        from .models import CompanyControl
        by_control_type = {}
        for ct in ['PREVENTIVE', 'DETECTIVE', 'CORRECTIVE']:
            control_ids = CompanyControl.objects.filter(
                subcategory__category__domain__framework=campaign.framework,
                control_type=ct,
                is_active=True
            ).values_list('id', flat=True)
            
            by_control_type[ct.lower()] = {
                'total': len(control_ids),
                'completed': responses.filter(control_id__in=control_ids).count()
            }
        
        return Response({
            'campaign_id': str(campaign.id),
            'name': campaign.name,
            'status': campaign.status,
            'overall': {
                'total_controls': campaign.total_controls,
                'completed': campaign.completed_controls,
                'pending': campaign.total_controls - campaign.completed_controls,
                'completion_percentage': float(campaign.completion_percentage),
                'compliance_score': float(campaign.compliance_score)
            },
            'by_compliance_status': by_status,
            'by_control_type': by_control_type
        })
    
    @action(detail=True, methods=['get'])
    def responses(self, request, pk=None):
        """
        Get all responses for campaign
        
        GET /api/v1/company/campaigns/{id}/responses/
        """
        campaign = self.get_object()
        
        responses = AssessmentResponse.objects.filter(
            campaign=campaign,
            is_active=True
        ).select_related('control')
        
        serializer = AssessmentResponseListSerializer(responses, many=True)
        
        return Response({
            'campaign_id': str(campaign.id),
            'total_responses': responses.count(),
            'responses': serializer.data
        })


# ============================================================================
# RESPONSE VIEWS
# ============================================================================

class AssessmentResponseViewSet(viewsets.ModelViewSet):
    """
    Assessment responses
    
    GET /api/v1/company/responses/
    POST /api/v1/company/responses/
    GET /api/v1/company/responses/{id}/
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign', 'control', 'compliance_status', 'remediation_required']
    search_fields = ['control__control_code', 'notes']
    ordering_fields = ['responded_at', 'compliance_status']
    ordering = ['-responded_at']
    
    def get_queryset(self):
        """Filter responses"""
        queryset = AssessmentResponse.objects.filter(
            is_active=True
        ).select_related('campaign', 'control', 'assignment')
        
        # Non-admins only see their own responses
        if not self.request.user.is_superuser:
            from user_management.models import TenantMembership
            
            tenant_slug = getattr(self.request, 'tenant_slug', None)
            
            try:
                membership = TenantMembership.objects.get(
                    user=self.request.user,
                    tenant_slug=tenant_slug,
                    is_active=True
                )
                
                # Admins/managers see all, others see only their own
                if not (membership.is_admin or membership.can_assign_controls):
                    queryset = queryset.filter(responded_by_user_id=self.request.user.id)
                    
            except TenantMembership.DoesNotExist:
                return AssessmentResponse.objects.none()
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AssessmentResponseListSerializer
        elif self.action == 'create':
            return AssessmentResponseCreateSerializer
        return AssessmentResponseDetailSerializer
    
    @action(detail=False, methods=['get'])
    def my_responses(self, request):
        """
        Get current user's responses
        
        GET /api/v1/company/responses/my_responses/
        """
        responses = AssessmentResponse.objects.filter(
            responded_by_user_id=request.user.id,
            is_active=True
        ).select_related('campaign', 'control').order_by('-responded_at')
        
        serializer = AssessmentResponseListSerializer(responses, many=True)
        
        return Response({
            'total': responses.count(),
            'responses': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """
        Review assessment response (Manager/Admin only)
        
        POST /api/v1/company/responses/{id}/review/
        {
            "review_notes": "Approved, good evidence"
        }
        """
        # Check permissions
        from user_management.models import TenantMembership
        tenant_slug = getattr(request, 'tenant_slug', None)
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            if not (membership.is_admin or membership.has_permission('review_responses')):
                return Response({
                    'error': 'You do not have permission to review responses'
                }, status=status.HTTP_403_FORBIDDEN)
                
        except TenantMembership.DoesNotExist:
            return Response({
                'error': 'Tenant membership not found'
            }, status=status.HTTP_403_FORBIDDEN)
        
        response = self.get_object()
        
        response.reviewed_by_user_id = request.user.id
        response.reviewed_at = timezone.now()
        response.review_notes = request.data.get('review_notes', '')
        response.save()
        
        return Response({
            'success': True,
            'message': 'Response reviewed',
            'response': AssessmentResponseDetailSerializer(response).data
        })


# ============================================================================
# EVIDENCE VIEWS
# ============================================================================

class EvidenceDocumentViewSet(viewsets.ModelViewSet):
    """
    Evidence documents
    
    GET /api/v1/company/evidence/
    POST /api/v1/company/evidence/
    GET /api/v1/company/evidence/{id}/
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['control', 'response', 'is_verified', 'is_archived']
    search_fields = ['title', 'description', 'tags', 'file_name']
    ordering_fields = ['uploaded_at', 'title']
    ordering = ['-uploaded_at']
    
    def get_queryset(self):
        """Filter evidence"""
        queryset = EvidenceDocument.objects.filter(
            is_active=True
        ).select_related('control', 'response')
        
        # Non-admins only see their own evidence
        if not self.request.user.is_superuser:
            from user_management.models import TenantMembership
            
            tenant_slug = getattr(self.request, 'tenant_slug', None)
            
            try:
                membership = TenantMembership.objects.get(
                    user=self.request.user,
                    tenant_slug=tenant_slug,
                    is_active=True
                )
                
                if not (membership.is_admin or membership.can_assign_controls):
                    queryset = queryset.filter(uploaded_by_user_id=self.request.user.id)
                    
            except TenantMembership.DoesNotExist:
                return EvidenceDocument.objects.none()
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EvidenceDocumentUploadSerializer
        return EvidenceDocumentSerializer
    
    @action(detail=False, methods=['get'])
    def my_evidence(self, request):
        """
        Get current user's uploaded evidence
        
        GET /api/v1/company/evidence/my_evidence/
        """
        evidence = EvidenceDocument.objects.filter(
            uploaded_by_user_id=request.user.id,
            is_active=True
        ).select_related('control').order_by('-uploaded_at')
        
        serializer = EvidenceDocumentSerializer(evidence, many=True)
        
        return Response({
            'total': evidence.count(),
            'evidence': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify evidence document (Manager/Admin only)
        
        POST /api/v1/company/evidence/{id}/verify/
        """
        # Check permissions
        from user_management.models import TenantMembership
        tenant_slug = getattr(request, 'tenant_slug', None)
        
        try:
            membership = TenantMembership.objects.get(
                user=request.user,
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            if not (membership.is_admin or membership.has_permission('manage_evidence')):
                return Response({
                    'error': 'You do not have permission to verify evidence'
                }, status=status.HTTP_403_FORBIDDEN)
                
        except TenantMembership.DoesNotExist:
            return Response({
                'error': 'Tenant membership not found'
            }, status=status.HTTP_403_FORBIDDEN)
        
        evidence = self.get_object()
        
        evidence.is_verified = True
        evidence.verified_by_user_id = request.user.id
        evidence.verified_at = timezone.now()
        evidence.save()
        
        return Response({
            'success': True,
            'message': 'Evidence verified',
            'evidence': EvidenceDocumentSerializer(evidence).data
        })
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """
        Archive evidence document
        
        POST /api/v1/company/evidence/{id}/archive/
        """
        evidence = self.get_object()
        
        evidence.is_archived = True
        evidence.archived_at = timezone.now()
        evidence.save()
        
        return Response({
            'success': True,
            'message': 'Evidence archived',
            'evidence': EvidenceDocumentSerializer(evidence).data
        })


# ============================================================================
# REPORT VIEWS
# ============================================================================

class ComplianceReportViewSet(viewsets.ModelViewSet):
    """
    Compliance reports
    
    GET /api/v1/company/reports/
    POST /api/v1/company/reports/
    GET /api/v1/company/reports/{id}/
    """
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['framework', 'campaign', 'report_type', 'is_final', 'is_published']
    search_fields = ['title', 'description']
    ordering_fields = ['generated_at', 'overall_compliance_score']
    ordering = ['-generated_at']
    
    def get_queryset(self):
        """Filter reports"""
        return ComplianceReport.objects.filter(
            is_active=True
        ).select_related('framework', 'campaign')
    
    def get_serializer_class(self):
        return ComplianceReportSerializer
    
    def get_permissions(self):
        """Require campaign management permission for create"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanCreateCampaigns()]
        return super().get_permissions()
    
    def create(self, request, *args, **kwargs):
        """
        Generate compliance report
        
        POST /api/v1/company/reports/
        {
            "framework": "uuid",
            "campaign": "uuid",
            "title": "Q1 2024 SOX Compliance Report",
            "report_type": "EXECUTIVE_SUMMARY",
            "report_format": "PDF"
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # TODO: Actual report generation logic
        # For now, create placeholder
        
        campaign = serializer.validated_data.get('campaign')
        
        report = ComplianceReport.objects.create(
            **serializer.validated_data,
            generated_by_user_id=request.user.id,
            generated_by_username=request.user.username,
            generated_at=timezone.now(),
            overall_compliance_score=campaign.compliance_score if campaign else Decimal('0'),
            total_controls=campaign.total_controls if campaign else 0,
            compliant_controls=campaign.compliant_count if campaign else 0,
            non_compliant_controls=campaign.non_compliant_count if campaign else 0,
            not_applicable_controls=campaign.not_applicable_count if campaign else 0,
            file_path=f'reports/placeholder.pdf',  # TODO: actual generation
            file_size=0
        )
        
        return Response(
            ComplianceReportSerializer(report).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish report
        
        POST /api/v1/company/reports/{id}/publish/
        """
        report = self.get_object()
        
        report.is_published = True
        report.is_final = True
        report.save()
        
        return Response({
            'success': True,
            'message': 'Report published',
            'report': ComplianceReportSerializer(report).data
        })
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download report
        
        GET /api/v1/company/reports/{id}/download/
        """
        report = self.get_object()
        
        # TODO: Return actual file download
        # For now, return file info
        
        return Response({
            'report_id': str(report.id),
            'title': report.title,
            'file_path': report.file_path,
            'file_size': report.file_size,
            'download_url': f'/media/{report.file_path}',  # TODO: signed URL
            'message': 'File download not yet implemented'
        })
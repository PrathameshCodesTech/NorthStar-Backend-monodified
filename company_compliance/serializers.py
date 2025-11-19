"""
Company Compliance Serializers
Handles tenant-specific compliance operations
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from .models import (
    CompanyFramework, CompanyDomain, CompanyCategory, CompanySubcategory,
    CompanyControl, CompanyAssessmentQuestion, CompanyEvidenceRequirement,
    ControlAssignment, AssessmentCampaign, AssessmentResponse,
    EvidenceDocument, ComplianceReport
)


# ============================================================================
# FRAMEWORK SERIALIZERS
# ============================================================================

class CompanyFrameworkListSerializer(serializers.ModelSerializer):
    """List of company frameworks"""
    
    domain_count = serializers.SerializerMethodField()
    control_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyFramework
        fields = [
            'id', 'name', 'full_name', 'version', 'status',
            'customization_level', 'is_customized',
            'domain_count', 'control_count', 'subscribed_at'
        ]
    
    def get_domain_count(self, obj):
        return obj.domains.filter(is_active=True).count()
    
    def get_control_count(self, obj):
        return CompanyControl.objects.filter(
            subcategory__category__domain__framework=obj,
            is_active=True
        ).count()


class CompanyFrameworkDetailSerializer(serializers.ModelSerializer):
    """Detailed framework with hierarchy"""
    
    statistics = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyFramework
        fields = [
            'id', 'name', 'full_name', 'description', 'version',
            'status', 'effective_date', 'customization_level',
            'is_customized', 'can_customize', 'statistics',
            'subscribed_at', 'created_at', 'is_active'
        ]
    
    def get_statistics(self, obj):
        """Get framework statistics"""
        controls = CompanyControl.objects.filter(
            subcategory__category__domain__framework=obj,
            is_active=True
        )
        
        return {
            'domains': obj.domains.filter(is_active=True).count(),
            'categories': CompanyCategory.objects.filter(
                domain__framework=obj,
                is_active=True
            ).count(),
            'subcategories': CompanySubcategory.objects.filter(
                category__domain__framework=obj,
                is_active=True
            ).count(),
            'controls': controls.count(),
            'customized_controls': controls.filter(is_customized=True).count(),
            'control_types': {
                'preventive': controls.filter(control_type='PREVENTIVE').count(),
                'detective': controls.filter(control_type='DETECTIVE').count(),
                'corrective': controls.filter(control_type='CORRECTIVE').count()
            }
        }


# ============================================================================
# CONTROL SERIALIZERS
# ============================================================================

class CompanyControlListSerializer(serializers.ModelSerializer):
    """List of company controls"""
    
    effective_title = serializers.SerializerMethodField()
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    has_assignments = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyControl
        fields = [
            'id', 'control_code', 'effective_title', 'subcategory_name',
            'control_type', 'frequency', 'risk_level',
            'is_customized', 'has_assignments', 'sort_order'
        ]
    
    def get_effective_title(self, obj):
        return obj.get_effective_title()
    
    def get_has_assignments(self, obj):
        return obj.assignments.filter(is_active=True).exists()


class CompanyControlDetailSerializer(serializers.ModelSerializer):
    """Detailed control with all info"""
    
    effective_title = serializers.SerializerMethodField()
    effective_description = serializers.SerializerMethodField()
    effective_objective = serializers.SerializerMethodField()
    subcategory = serializers.SerializerMethodField()
    assessment_questions = serializers.SerializerMethodField()
    evidence_requirements = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyControl
        fields = [
            'id', 'control_code', 'title', 'effective_title',
            'description', 'effective_description',
            'objective', 'effective_objective',
            'control_type', 'frequency', 'risk_level',
            'subcategory', 'is_customized', 'can_customize',
            'custom_title', 'custom_description', 'custom_objective',
            'custom_procedures', 'assessment_questions',
            'evidence_requirements', 'assignment_count',
            'created_at', 'updated_at'
        ]
    
    def get_effective_title(self, obj):
        return obj.get_effective_title()
    
    def get_effective_description(self, obj):
        return obj.get_effective_description()
    
    def get_effective_objective(self, obj):
        return obj.get_effective_objective()
    
    def get_subcategory(self, obj):
        if obj.subcategory:
            return {
                'id': str(obj.subcategory.id),
                'code': obj.subcategory.code,
                'name': obj.subcategory.name
            }
        return None
    
    def get_assessment_questions(self, obj):
        questions = obj.assessment_questions.filter(is_active=True).order_by('sort_order')
        return [{
            'id': str(q.id),
            'question_type': q.question_type,
            'question': q.question,
            'guidance': q.guidance,
            'is_mandatory': q.is_mandatory
        } for q in questions]
    
    def get_evidence_requirements(self, obj):
        evidence = obj.evidence_requirements.filter(is_active=True).order_by('sort_order')
        return [{
            'id': str(e.id),
            'title': e.title,
            'description': e.description,
            'evidence_type': e.evidence_type,
            'is_mandatory': e.is_mandatory
        } for e in evidence]
    
    def get_assignment_count(self, obj):
        return obj.assignments.filter(is_active=True).count()


class CompanyControlCustomizeSerializer(serializers.ModelSerializer):
    """Customize control"""
    
    class Meta:
        model = CompanyControl
        fields = [
            'custom_title', 'custom_description',
            'custom_objective', 'custom_procedures'
        ]
    
    def validate(self, data):
        """Ensure control can be customized"""
        if not self.instance.can_customize:
            raise serializers.ValidationError(
                "This control cannot be customized in your subscription plan"
            )
        return data
    
    def update(self, instance, validated_data):
        """Mark as customized and update"""
        instance.is_customized = True
        instance.customized_at = timezone.now()
        
        # Get user from context
        request = self.context.get('request')
        if request and request.user:
            instance.customized_by_user_id = request.user.id
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        
        instance.save()
        return instance


# ============================================================================
# ASSIGNMENT SERIALIZERS
# ============================================================================

class ControlAssignmentListSerializer(serializers.ModelSerializer):
    """List of assignments"""
    
    control_code = serializers.CharField(source='control.control_code', read_only=True)
    control_title = serializers.SerializerMethodField()
    assigned_to_name = serializers.CharField(source='assigned_to_username', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = ControlAssignment
        fields = [
            'id', 'control', 'control_code', 'control_title',
            'assigned_to_name', 'status', 'priority',
            'due_date', 'is_overdue', 'completion_date', 'created_at'
        ]
    
    def get_control_title(self, obj):
        return obj.control.get_effective_title()
    
    def get_is_overdue(self, obj):
        return obj.is_overdue


class ControlAssignmentDetailSerializer(serializers.ModelSerializer):
    """Detailed assignment"""
    
    control = CompanyControlDetailSerializer(read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to_username', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = ControlAssignment
        fields = [
            'id', 'control', 'assigned_to_user_id', 'assigned_to_name',
            'assigned_to_email', 'assigned_by_user_id', 'assigned_by_name',
            'status', 'priority', 'due_date', 'completion_date',
            'notes', 'completion_notes', 'notification_sent',
            'reminder_sent', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['assigned_by_user_id', 'notification_sent', 'reminder_sent']
    
    def get_assigned_by_name(self, obj):
        if obj.assigned_by_user_id:
            try:
                user = User.objects.get(id=obj.assigned_by_user_id)
                return user.get_full_name() or user.username
            except User.DoesNotExist:
                pass
        return None
    
    def get_is_overdue(self, obj):
        return obj.is_overdue


class ControlAssignmentCreateSerializer(serializers.ModelSerializer):
    """Create new assignment"""
    
    class Meta:
        model = ControlAssignment
        fields = [
            'control', 'assigned_to_user_id', 'assigned_to_username',
            'assigned_to_email', 'status', 'priority', 'due_date', 'notes'
        ]
    
    def validate_assigned_to_user_id(self, value):
        """Validate user exists"""
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value
    
    def validate(self, data):
        """Validate assignment doesn't already exist"""
        control = data.get('control')
        user_id = data.get('assigned_to_user_id')
        
        # Check for existing active assignment
        if ControlAssignment.objects.filter(
            control=control,
            assigned_to_user_id=user_id,
            is_active=True,
            status__in=['PENDING', 'IN_PROGRESS']
        ).exists():
            raise serializers.ValidationError(
                "Active assignment already exists for this user and control"
            )
        
        return data
    
    def create(self, validated_data):
        """Create assignment with assigned_by"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['assigned_by_user_id'] = request.user.id
        
        return super().create(validated_data)


class ControlAssignmentUpdateSerializer(serializers.ModelSerializer):
    """Update assignment status"""
    
    class Meta:
        model = ControlAssignment
        fields = ['status', 'completion_notes']
    
    def validate_status(self, value):
        """Validate status transition"""
        instance = self.instance
        if instance:
            current = instance.status
            
            # Define valid transitions
            valid_transitions = {
                'PENDING': ['IN_PROGRESS', 'CANCELLED'],
                'IN_PROGRESS': ['COMPLETED', 'CANCELLED'],
                'COMPLETED': [],  # Cannot change from completed
                'CANCELLED': []   # Cannot change from cancelled
            }
            
            if value != current:
                allowed = valid_transitions.get(current, [])
                if value not in allowed:
                    raise serializers.ValidationError(
                        f"Cannot transition from {current} to {value}"
                    )
        
        return value
    
    def update(self, instance, validated_data):
        """Update with completion timestamp"""
        if validated_data.get('status') == 'COMPLETED' and instance.status != 'COMPLETED':
            instance.completion_date = timezone.now()
        
        return super().update(instance, validated_data)


# ============================================================================
# CAMPAIGN SERIALIZERS
# ============================================================================

class AssessmentCampaignListSerializer(serializers.ModelSerializer):
    """List of campaigns"""
    
    framework_name = serializers.CharField(source='framework.name', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentCampaign
        fields = [
            'id', 'name', 'framework', 'framework_name',
            'status', 'start_date', 'end_date',
            'completion_percentage', 'progress_percentage',
            'compliance_score', 'created_at'
        ]
    
    def get_progress_percentage(self, obj):
        return obj.completion_percentage


class AssessmentCampaignDetailSerializer(serializers.ModelSerializer):
    """Detailed campaign with stats"""
    
    framework = CompanyFrameworkListSerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by_username', read_only=True)
    statistics = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentCampaign
        fields = [
            'id', 'framework', 'name', 'description',
            'status', 'start_date', 'end_date',
            'total_controls', 'completed_controls', 'completion_percentage',
            'compliant_count', 'non_compliant_count', 'not_applicable_count',
            'compliance_score', 'statistics',
            'created_by_username', 'created_by_name',
            'created_at', 'updated_at'
        ]
    
    def get_statistics(self, obj):
        """Get detailed statistics"""
        return {
            'total': obj.total_controls,
            'completed': obj.completed_controls,
            'pending': obj.total_controls - obj.completed_controls,
            'completion_rate': obj.completion_percentage,
            'compliance': {
                'compliant': obj.compliant_count,
                'non_compliant': obj.non_compliant_count,
                'not_applicable': obj.not_applicable_count,
                'score': obj.compliance_score
            }
        }


class AssessmentCampaignCreateSerializer(serializers.ModelSerializer):
    """Create new campaign"""
    
    class Meta:
        model = AssessmentCampaign
        fields = [
            'framework', 'name', 'description',
            'start_date', 'end_date'
        ]
    
    def validate(self, data):
        """Validate dates"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })
        
        return data
    
    def create(self, validated_data):
        """Create campaign with initial counts"""
        request = self.context.get('request')
        
        framework = validated_data['framework']
        
        # Count total controls in framework
        total_controls = CompanyControl.objects.filter(
            subcategory__category__domain__framework=framework,
            is_active=True
        ).count()
        
        campaign = AssessmentCampaign.objects.create(
            **validated_data,
            created_by_user_id=request.user.id if request and request.user else None,
            created_by_username=request.user.username if request and request.user else '',
            total_controls=total_controls,
            completed_controls=0,
            completion_percentage=Decimal('0.00'),
            compliant_count=0,
            non_compliant_count=0,
            not_applicable_count=0,
            compliance_score=Decimal('0.00'),
            status='PLANNED'
        )
        
        return campaign


# ============================================================================
# RESPONSE SERIALIZERS
# ============================================================================

class AssessmentResponseListSerializer(serializers.ModelSerializer):
    """List of responses"""
    
    control_code = serializers.CharField(source='control.control_code', read_only=True)
    control_title = serializers.SerializerMethodField()
    responded_by_name = serializers.CharField(source='responded_by_username', read_only=True)
    
    class Meta:
        model = AssessmentResponse
        fields = [
            'id', 'campaign', 'control', 'control_code', 'control_title',
            'response', 'compliance_status', 'confidence_level',
            'remediation_required', 'responded_by_name', 'responded_at'
        ]
    
    def get_control_title(self, obj):
        return obj.control.get_effective_title()


class AssessmentResponseDetailSerializer(serializers.ModelSerializer):
    """Detailed response"""
    
    control = CompanyControlDetailSerializer(read_only=True)
    assignment = ControlAssignmentDetailSerializer(read_only=True)
    responded_by_name = serializers.CharField(source='responded_by_username', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AssessmentResponse
        fields = [
            'id', 'campaign', 'control', 'assignment',
            'response', 'compliance_status', 'confidence_level',
            'notes', 'issues_identified', 'remediation_required',
            'remediation_plan', 'responded_by_user_id', 'responded_by_name',
            'responded_at', 'reviewed_by_user_id', 'reviewed_by_name',
            'reviewed_at', 'review_notes', 'created_at', 'updated_at'
        ]
    
    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by_user_id:
            try:
                user = User.objects.get(id=obj.reviewed_by_user_id)
                return user.get_full_name() or user.username
            except User.DoesNotExist:
                pass
        return None


class AssessmentResponseCreateSerializer(serializers.ModelSerializer):
    """Submit assessment response"""
    
    class Meta:
        model = AssessmentResponse
        fields = [
            'campaign', 'control', 'assignment',
            'response', 'compliance_status', 'confidence_level',
            'notes', 'issues_identified', 'remediation_required',
            'remediation_plan'
        ]
    
    def validate(self, data):
        """Validate response doesn't already exist"""
        campaign = data.get('campaign')
        control = data.get('control')
        
        if AssessmentResponse.objects.filter(
            campaign=campaign,
            control=control,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                "Response already exists for this control in this campaign"
            )
        
        return data
    
    def create(self, validated_data):
        """Create response with respondent info"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['responded_by_user_id'] = request.user.id
            validated_data['responded_by_username'] = request.user.username
            validated_data['responded_at'] = timezone.now()
        
        response = super().create(validated_data)
        
        # Update campaign statistics
        self._update_campaign_stats(response.campaign)
        
        return response
    
    def _update_campaign_stats(self, campaign):
        """Update campaign completion and compliance stats"""
        responses = AssessmentResponse.objects.filter(
            campaign=campaign,
            is_active=True
        )
        
        campaign.completed_controls = responses.count()
        
        if campaign.total_controls > 0:
            campaign.completion_percentage = Decimal(
                (campaign.completed_controls / campaign.total_controls) * 100
            )
        
        # Count compliance statuses
        campaign.compliant_count = responses.filter(compliance_status='COMPLIANT').count()
        campaign.non_compliant_count = responses.filter(compliance_status='NON_COMPLIANT').count()
        campaign.not_applicable_count = responses.filter(compliance_status='NOT_APPLICABLE').count()
        
        # Calculate compliance score
        total_assessed = campaign.compliant_count + campaign.non_compliant_count
        if total_assessed > 0:
            campaign.compliance_score = Decimal(
                (campaign.compliant_count / total_assessed) * 100
            )
        
        campaign.save()


# ============================================================================
# EVIDENCE SERIALIZERS
# ============================================================================

class EvidenceDocumentSerializer(serializers.ModelSerializer):
    """Evidence document"""
    
    control_code = serializers.CharField(source='control.control_code', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by_username', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = EvidenceDocument
        fields = [
            'id', 'control', 'control_code', 'response',
            'title', 'description', 'tags',
            'file_name', 'file_path', 'file_size', 'file_size_display',
            'file_type', 'file_extension',
            'is_verified', 'is_archived',
            'uploaded_by_name', 'uploaded_at',
            'created_at'
        ]
        read_only_fields = [
            'file_size', 'file_type', 'file_extension',
            'uploaded_by_user_id', 'uploaded_at'
        ]
    
    def get_file_size_display(self, obj):
        """Human-readable file size"""
        size_kb = obj.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        size_mb = size_kb / 1024
        return f"{size_mb:.1f} MB"


class EvidenceDocumentUploadSerializer(serializers.ModelSerializer):
    """Upload evidence document"""
    
    file = serializers.FileField(write_only=True)
    
    class Meta:
        model = EvidenceDocument
        fields = [
            'control', 'response', 'title', 'description',
            'tags', 'file'
        ]
    
    def create(self, validated_data):
        """Handle file upload"""
        file = validated_data.pop('file')
        request = self.context.get('request')
        
        # TODO: Upload file to storage (S3, etc.)
        # For now, store file info
        
        evidence = EvidenceDocument.objects.create(
            **validated_data,
            file_name=file.name,
            file_path=f'evidence/{file.name}',  # TODO: actual storage path
            file_size=file.size,
            file_type=file.content_type,
            file_extension=file.name.split('.')[-1] if '.' in file.name else '',
            uploaded_by_user_id=request.user.id if request and request.user else None,
            uploaded_by_username=request.user.username if request and request.user else '',
            uploaded_at=timezone.now()
        )
        
        return evidence


# ============================================================================
# REPORT SERIALIZERS
# ============================================================================

class ComplianceReportSerializer(serializers.ModelSerializer):
    """Compliance report"""
    
    framework_name = serializers.CharField(source='framework.name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by_username', read_only=True)
    
    class Meta:
        model = ComplianceReport
        fields = [
            'id', 'framework', 'framework_name', 'campaign', 'campaign_name',
            'title', 'description', 'report_type', 'report_format',
            'file_path', 'file_size', 'overall_compliance_score',
            'total_controls', 'compliant_controls', 'non_compliant_controls',
            'not_applicable_controls', 'report_period_start', 'report_period_end',
            'is_final', 'is_published', 'generated_by_name', 'generated_at',
            'created_at'
        ]
        read_only_fields = [
            'file_size', 'generated_by_user_id', 'generated_at'
        ]
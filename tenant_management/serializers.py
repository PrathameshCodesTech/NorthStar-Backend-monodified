"""
Tenant Management Serializers
Handles validation and serialization for tenant operations
"""

from rest_framework import serializers
from django.core.validators import EmailValidator
from .models import (
    SubscriptionPlan, TenantDatabaseInfo, FrameworkSubscription,
    TenantUsageLog, TenantBillingHistory
)
from .validators import validate_and_normalize_slug
from django.core.exceptions import ValidationError as DjangoValidationError


# ============================================================================
# SUBSCRIPTION PLAN SERIALIZERS
# ============================================================================

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Subscription plan details"""
    
    discount_percentage = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'code', 'name', 'description',
            'monthly_price', 'annual_price', 'discount_percentage',
            'max_users', 'max_frameworks', 'max_controls', 'storage_gb',
            'default_isolation_mode', 'default_customization_level',
            'support_level', 'features', 'is_active', 'sort_order'
        ]
        read_only_fields = ['id']
    
    def get_discount_percentage(self, obj):
        """Calculate annual discount percentage"""
        if obj.annual_price and obj.monthly_price:
            monthly_total = obj.monthly_price * 12
            discount = ((monthly_total - obj.annual_price) / monthly_total) * 100
            return round(discount, 1)
        return 0
    
    def get_features(self, obj):
        """List enabled features"""
        features = []
        if obj.can_create_custom_frameworks:
            features.append('Custom Frameworks')
        if obj.can_customize_controls:
            features.append('Control Customization')
        if obj.has_api_access:
            features.append('API Access')
        if obj.has_advanced_reporting:
            features.append('Advanced Reporting')
        if obj.has_sso:
            features.append('SSO')
        return features


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """Simplified plan listing"""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'code', 'name', 'monthly_price', 'annual_price',
            'max_users', 'max_frameworks', 'is_active'
        ]


# ============================================================================
# TENANT SERIALIZERS
# ============================================================================

class TenantCreateSerializer(serializers.Serializer):
    """Create new tenant - input validation"""
    
    tenant_slug = serializers.CharField(
        max_length=50,
        required=True,
        help_text="Unique identifier (3-50 chars, lowercase, hyphens only)"
    )
    company_name = serializers.CharField(
        max_length=200,
        required=True,
        help_text="Full company name"
    )
    company_email = serializers.EmailField(
        required=True,
        validators=[EmailValidator()],
        help_text="Primary contact email"
    )
    company_phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="Contact phone number"
    )
    subscription_plan_code = serializers.CharField(
        max_length=20,
        default='BASIC',
        help_text="Plan code: BASIC, PROFESSIONAL, or ENTERPRISE"
    )
    
    def validate_tenant_slug(self, value):
        """Validate and normalize tenant slug"""
        try:
            normalized_slug = validate_and_normalize_slug(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))
        
        # Check if slug already exists
        if TenantDatabaseInfo.objects.filter(tenant_slug=normalized_slug).exists():
            raise serializers.ValidationError(
                f"Tenant with slug '{normalized_slug}' already exists"
            )
        
        return normalized_slug
    
    def validate_subscription_plan_code(self, value):
        """Validate subscription plan exists"""
        try:
            SubscriptionPlan.objects.get(code=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(
                f"Subscription plan '{value}' not found or inactive"
            )
        return value
    
    def validate_company_name(self, value):
        """Validate company name"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Company name too short (min 2 characters)")
        
        # Check for invalid characters
        invalid_chars = '<>"\'&'
        if any(char in value for char in invalid_chars):
            raise serializers.ValidationError(
                f"Company name contains invalid characters: {invalid_chars}"
            )
        
        return value.strip()
    
    def create(self, validated_data):
        """Create and provision tenant"""
        from .tenant_utils import provision_tenant
        
        tenant_slug = validated_data['tenant_slug']
        company_name = validated_data['company_name']
        subscription_plan_code = validated_data['subscription_plan_code']
        
        # Provision tenant (creates schema/database, runs migrations)
        result = provision_tenant(
            tenant_slug=tenant_slug,
            company_name=company_name,
            subscription_plan_code=subscription_plan_code
        )
        
        if not result['success']:
            raise serializers.ValidationError(
                f"Provisioning failed: {result.get('error', 'Unknown error')}"
            )
        
        # Update additional fields
        tenant_info = result['tenant_info']
        tenant_info.company_email = validated_data['company_email']
        tenant_info.company_phone = validated_data.get('company_phone', '')
        tenant_info.save()
        
        return tenant_info


class TenantDetailSerializer(serializers.ModelSerializer):
    """Detailed tenant information"""
    
    subscription_plan = SubscriptionPlanSerializer(read_only=True)
    provisioning_status_display = serializers.CharField(
        source='get_provisioning_status_display',
        read_only=True
    )
    subscription_status_display = serializers.CharField(
        source='get_subscription_status_display',
        read_only=True
    )
    usage_summary = serializers.SerializerMethodField()
    limits_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantDatabaseInfo
        fields = [
            'id', 'tenant_slug', 'company_name', 'company_email', 'company_phone',
            'subscription_plan', 'subscription_status', 'subscription_status_display',
            'subscription_start_date', 'subscription_end_date', 'trial_end_date',
            'provisioning_status', 'provisioning_status_display', 'provisioning_error',
            'isolation_mode', 'schema_name', 'database_name',
            'current_user_count', 'current_framework_count', 'current_control_count',
            'storage_used_gb', 'usage_summary', 'limits_summary',
            'provisioned_at', 'last_health_check',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = [
            'id', 'provisioning_status', 'isolation_mode', 'schema_name',
            'database_name', 'provisioned_at', 'last_health_check',
            'created_at', 'updated_at'
        ]
    
    def get_usage_summary(self, obj):
        """Current usage vs limits"""
        plan = obj.subscription_plan
        return {
            'users': {
                'current': obj.current_user_count,
                'limit': plan.max_users if plan.max_users > 0 else None,
                'percentage': (obj.current_user_count / plan.max_users * 100) 
                    if plan.max_users > 0 else 0
            },
            'frameworks': {
                'current': obj.current_framework_count,
                'limit': plan.max_frameworks if plan.max_frameworks > 0 else None,
                'percentage': (obj.current_framework_count / plan.max_frameworks * 100)
                    if plan.max_frameworks > 0 else 0
            },
            'storage': {
                'current_gb': float(obj.storage_used_gb),
                'limit_gb': plan.storage_gb,
                'percentage': (float(obj.storage_used_gb) / plan.storage_gb * 100)
                    if plan.storage_gb > 0 else 0
            }
        }
    
    def get_limits_summary(self, obj):
        """Plan limits"""
        plan = obj.subscription_plan
        return {
            'max_users': plan.max_users if plan.max_users > 0 else 'Unlimited',
            'max_frameworks': plan.max_frameworks if plan.max_frameworks > 0 else 'Unlimited',
            'max_controls': plan.max_controls if plan.max_controls > 0 else 'Unlimited',
            'storage_gb': plan.storage_gb
        }


class TenantListSerializer(serializers.ModelSerializer):
    """Simplified tenant listing"""
    
    subscription_plan_name = serializers.CharField(
        source='subscription_plan.name',
        read_only=True
    )
    
    class Meta:
        model = TenantDatabaseInfo
        fields = [
            'id', 'tenant_slug', 'company_name', 'company_email',
            'subscription_plan_name', 'subscription_status', 'provisioning_status',
            'isolation_mode', 'current_user_count', 'current_framework_count',
            'created_at', 'is_active'
        ]


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Update tenant information"""
    
    class Meta:
        model = TenantDatabaseInfo
        fields = [
            'company_name', 'company_email', 'company_phone',
            'subscription_status'
        ]
    
    def validate_subscription_status(self, value):
        """Validate status transitions"""
        instance = self.instance
        if instance:
            # Validate status transitions
            valid_transitions = {
                'TRIAL': ['ACTIVE', 'CANCELLED', 'EXPIRED'],
                'ACTIVE': ['SUSPENDED', 'CANCELLED'],
                'SUSPENDED': ['ACTIVE', 'CANCELLED'],
                'CANCELLED': [],  # Can't reactivate from cancelled
                'EXPIRED': ['ACTIVE']  # Can renew
            }
            
            current_status = instance.subscription_status
            if value != current_status:
                allowed = valid_transitions.get(current_status, [])
                if value not in allowed:
                    raise serializers.ValidationError(
                        f"Cannot transition from {current_status} to {value}"
                    )
        
        return value


# ============================================================================
# FRAMEWORK SUBSCRIPTION SERIALIZERS
# ============================================================================

class FrameworkSubscriptionSerializer(serializers.ModelSerializer):
    """Framework subscription details"""
    
    tenant_name = serializers.CharField(source='tenant.company_name', read_only=True)
    upgrade_available = serializers.SerializerMethodField()
    
    class Meta:
        model = FrameworkSubscription
        fields = [
            'id', 'tenant', 'tenant_name', 'framework_id', 'framework_name',
            'framework_version', 'current_version', 'latest_available_version',
            'customization_level', 'subscription_type', 'addon_price',
            'upgrade_status', 'upgrade_available', 'has_customizations',
            'customized_controls_count', 'status', 'subscribed_at'
        ]
        read_only_fields = [
            'id', 'current_version', 'upgrade_status', 'has_customizations',
            'customized_controls_count', 'subscribed_at'
        ]
    
    def get_upgrade_available(self, obj):
        """Check if upgrade is available"""
        return obj.upgrade_status == 'UPGRADE_AVAILABLE'


class FrameworkSubscribeSerializer(serializers.Serializer):
    """Subscribe tenant to framework"""
    
    framework_id = serializers.UUIDField(required=True)
    customization_level = serializers.ChoiceField(
        choices=['VIEW_ONLY', 'CONTROL_LEVEL', 'FULL'],
        default='CONTROL_LEVEL'
    )
    
    def validate_framework_id(self, value):
        """Validate framework exists"""
        from templates_host.models import Framework
        
        try:
            Framework.objects.get(id=value, is_active=True, status='ACTIVE')
        except Framework.DoesNotExist:
            raise serializers.ValidationError("Framework not found or inactive")
        
        return value
    
    def validate(self, data):
        """Validate subscription is allowed"""
        tenant = self.context.get('tenant')
        framework_id = data['framework_id']
        
        # Check if already subscribed
        if FrameworkSubscription.objects.filter(
            tenant=tenant,
            framework_id=framework_id,
            status='ACTIVE'
        ).exists():
            raise serializers.ValidationError(
                "Tenant already subscribed to this framework"
            )
        
        # Check plan limits
        plan = tenant.subscription_plan
        if plan.max_frameworks > 0:
            current_count = FrameworkSubscription.objects.filter(
                tenant=tenant,
                status='ACTIVE'
            ).count()
            
            if current_count >= plan.max_frameworks:
                raise serializers.ValidationError(
                    f"Framework limit reached ({plan.max_frameworks}). "
                    f"Upgrade plan or remove existing frameworks."
                )
        
        # Validate customization level is allowed by plan
        customization_level = data['customization_level']
        if customization_level == 'FULL' and not plan.can_create_custom_frameworks:
            raise serializers.ValidationError(
                "Full customization not allowed in your plan. Upgrade to Enterprise."
            )
        
        return data
    
    def create(self, validated_data):
        """Create framework subscription and copy to tenant"""
        from templates_host.distribution_utils import copy_framework_to_tenant
        
        tenant = self.context['tenant']
        framework_id = validated_data['framework_id']
        customization_level = validated_data['customization_level']
        
        # Copy framework to tenant schema/database
        result = copy_framework_to_tenant(
            tenant=tenant,
            framework_id=framework_id,
            customization_level=customization_level
        )
        
        if not result['success']:
            raise serializers.ValidationError(
                f"Failed to copy framework: {result.get('error', 'Unknown error')}"
            )
        
        # Create subscription record
        from templates_host.models import Framework
        framework = Framework.objects.get(id=framework_id)
        
        subscription = FrameworkSubscription.objects.create(
            tenant=tenant,
            framework_id=framework_id,
            framework_name=framework.name,
            framework_version=framework.version,
            current_version=framework.version,
            latest_available_version=framework.version,
            customization_level=customization_level,
            subscription_type='INCLUDED',
            status='ACTIVE'
        )
        
        # Update tenant counts
        tenant.current_framework_count = FrameworkSubscription.objects.filter(
            tenant=tenant,
            status='ACTIVE'
        ).count()
        tenant.save()
        
        return subscription


# ============================================================================
# USAGE & BILLING SERIALIZERS
# ============================================================================

class TenantUsageLogSerializer(serializers.ModelSerializer):
    """Usage log entry"""
    
    class Meta:
        model = TenantUsageLog
        fields = [
            'id', 'log_date', 'user_count', 'framework_count', 'control_count',
            'assessment_count', 'evidence_count', 'storage_used_gb', 'api_calls_count'
        ]


class TenantBillingHistorySerializer(serializers.ModelSerializer):
    """Billing history entry"""
    
    class Meta:
        model = TenantBillingHistory
        fields = [
            'id', 'billing_period_start', 'billing_period_end',
            'base_plan_amount', 'addon_frameworks_amount', 'addon_users_amount',
            'addon_storage_amount', 'total_amount', 'payment_status',
            'payment_date', 'payment_method', 'invoice_number', 'invoice_url'
        ]
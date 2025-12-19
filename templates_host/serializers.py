"""
Framework Template Serializers
Handles serialization for framework templates (SuperAdmin only)
"""

from rest_framework import serializers
from .models import (
    Framework, FrameworkCategory, Domain, Category, Subcategory,
    Control, AssessmentQuestion, EvidenceRequirement
)


# ============================================================================
# FRAMEWORK CATEGORY SERIALIZERS
# ============================================================================

class FrameworkCategorySerializer(serializers.ModelSerializer):
    """Framework category (Financial, Security, etc.)"""
    
    class Meta:
        model = FrameworkCategory
        fields = [
            'id', 'name', 'code', 'description',
            'icon', 'color', 'sort_order', 'is_active'
        ]


# ============================================================================
# FRAMEWORK SERIALIZERS
# ============================================================================

class FrameworkBasicSerializer(serializers.ModelSerializer):
    """Basic framework info for listings"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Framework
        fields = [
            'id', 'name', 'full_name', 'version', 'status',
            'category', 'category_name', 'effective_date', 'is_active'
        ]


class FrameworkDetailSerializer(serializers.ModelSerializer):
    """Detailed framework with statistics"""
    
    category = FrameworkCategorySerializer(read_only=True)
    domain_count = serializers.SerializerMethodField()
    control_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Framework
        fields = [
            'id', 'name', 'full_name', 'description', 'version',
            'status', 'effective_date', 'category',
            'domain_count', 'control_count',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_domain_count(self, obj):
        return obj.domains.filter(is_active=True).count()
    
    def get_control_count(self, obj):
        return Control.objects.filter(
            subcategory__category__domain__framework=obj,
            is_active=True
        ).count()


class FrameworkCreateSerializer(serializers.ModelSerializer):
    """Create new framework"""
    
    class Meta:
        model = Framework
        fields = [
            'name', 'full_name', 'description', 'version',
            'status', 'effective_date', 'category',"applicable_industries", "applicable_regions", "compliance_authority",
        ]
    
    def validate_name(self, value):
        """Ensure unique framework name"""
        if Framework.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f"Framework with name '{value}' already exists"
            )
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


# ============================================================================
# DOMAIN SERIALIZERS
# ============================================================================

class DomainBasicSerializer(serializers.ModelSerializer):
    """Basic domain info"""
    
    framework_name = serializers.CharField(source='framework.name', read_only=True)
    
    class Meta:
        model = Domain
        fields = [
            'id', 'code', 'name', 'framework', 'framework_name',
            'sort_order', 'is_active'
        ]


class DomainDetailSerializer(serializers.ModelSerializer):
    """Detailed domain with framework info"""
    
    framework = FrameworkBasicSerializer(read_only=True)
    category_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Domain
        fields = [
            'id', 'framework', 'code', 'name', 'description',
            'sort_order', 'category_count',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_category_count(self, obj):
        return obj.categories.filter(is_active=True).count()


class DomainCreateSerializer(serializers.ModelSerializer):
    """Create new domain - framework optional"""
    
    class Meta:
        model = Domain
        fields = ['framework', 'code', 'name', 'description', 'sort_order']
    
    def validate(self, data):
        """Validate unique code within framework (only when framework is set)"""
        framework = data.get('framework')
        code = data.get('code')
        
        # Only check uniqueness if framework is provided
        if framework:
            if Domain.objects.filter(framework=framework, code=code).exists():
                raise serializers.ValidationError({
                    'code': f"Domain with code '{code}' already exists in this framework"
                })
        
        return data


# ============================================================================
# CATEGORY SERIALIZERS
# ============================================================================

class CategoryBasicSerializer(serializers.ModelSerializer):
    """Basic category info"""
    
    domain_code = serializers.CharField(source='domain.code', read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'code', 'name', 'domain', 'domain_code',
            'sort_order', 'is_active'
        ]


class CategoryDetailSerializer(serializers.ModelSerializer):
    """Detailed category with domain info"""
    
    domain = DomainBasicSerializer(read_only=True)
    subcategory_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'domain', 'code', 'name', 'description',
            'sort_order', 'subcategory_count',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_subcategory_count(self, obj):
        return obj.subcategories.filter(is_active=True).count()


class CategoryCreateSerializer(serializers.ModelSerializer):
    """Create new category - domain optional"""
    
    class Meta:
        model = Category
        fields = ['domain', 'code', 'name', 'description', 'sort_order']
    
    def validate(self, data):
        """Validate unique code within domain (only when domain is set)"""
        domain = data.get('domain')
        code = data.get('code')
        
        # Only check uniqueness if domain is provided
        if domain:
            if Category.objects.filter(domain=domain, code=code).exists():
                raise serializers.ValidationError({
                    'code': f"Category with code '{code}' already exists in this domain"
                })
        
        return data


# ============================================================================
# SUBCATEGORY SERIALIZERS
# ============================================================================

class SubcategoryBasicSerializer(serializers.ModelSerializer):
    """Basic subcategory info"""
    
    category_code = serializers.CharField(source='category.code', read_only=True)
    
    class Meta:
        model = Subcategory
        fields = [
            'id', 'code', 'name', 'category', 'category_code',
            'sort_order', 'is_active'
        ]


class SubcategoryDetailSerializer(serializers.ModelSerializer):
    """Detailed subcategory with category info"""
    
    category = CategoryBasicSerializer(read_only=True)
    control_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Subcategory
        fields = [
            'id', 'category', 'code', 'name', 'description',
            'sort_order', 'control_count',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_control_count(self, obj):
        return obj.controls.filter(is_active=True).count()


class SubcategoryCreateSerializer(serializers.ModelSerializer):
    """Create new subcategory - category optional"""
    
    class Meta:
        model = Subcategory
        fields = ['category', 'code', 'name', 'description', 'sort_order']
    
    def validate(self, data):
        """Validate unique code within category (only when category is set)"""
        category = data.get('category')
        code = data.get('code')
        
        # Only check uniqueness if category is provided
        if category:
            if Subcategory.objects.filter(category=category, code=code).exists():
                raise serializers.ValidationError({
                    'code': f"Subcategory with code '{code}' already exists in this category"
                })
        
        return data


# ============================================================================
# ASSESSMENT QUESTION SERIALIZERS
# ============================================================================

class AssessmentQuestionSerializer(serializers.ModelSerializer):
    """Assessment question for controls"""
    
    class Meta:
        model = AssessmentQuestion
        fields = [
            'id', 'control', 'question_type', 'question',
             'is_mandatory', 'sort_order',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']


# ============================================================================
# EVIDENCE REQUIREMENT SERIALIZERS
# ============================================================================

class EvidenceRequirementSerializer(serializers.ModelSerializer):
    """Evidence requirement for controls"""
    
    class Meta:
        model = EvidenceRequirement
        fields = [
            'id', 'control', 'title', 'description', 'evidence_type',
            'file_format', 'is_mandatory', 'sort_order',
            'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']


# ============================================================================
# CONTROL SERIALIZERS
# ============================================================================

class ControlBasicSerializer(serializers.ModelSerializer):
    """Basic control info for listings"""
    
    subcategory_code = serializers.CharField(source='subcategory.code', read_only=True)
    
    class Meta:
        model = Control
        fields = [
            'id', 'control_code', 'title', 'control_type',
            'frequency', 'risk_level', 'subcategory', 'subcategory_code',
            'sort_order', 'is_active'
        ]


class ControlDetailSerializer(serializers.ModelSerializer):
    """Detailed control with questions and evidence"""
    
    subcategory = SubcategoryBasicSerializer(read_only=True)
    assessment_questions = AssessmentQuestionSerializer(many=True, read_only=True)
    evidence_requirements = EvidenceRequirementSerializer(many=True, read_only=True)
    hierarchy = serializers.SerializerMethodField()
    
    class Meta:
        model = Control
        fields = [
            'id', 'subcategory', 'control_code', 'title', 'description',
            'objective', 'control_type', 'frequency', 'risk_level',
            'sort_order', 'assessment_questions', 'evidence_requirements',
            'hierarchy', 'created_at', 'updated_at', 'created_by',
            'updated_by', 'is_active'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_hierarchy(self, obj):
        """Get full hierarchy path"""
        if not obj.subcategory:
            return None
        
        subcat = obj.subcategory
        cat = subcat.category if subcat else None
        dom = cat.domain if cat else None
        fw = dom.framework if dom else None
        
        return {
            'framework': {
                'id': str(fw.id) if fw else None,
                'name': fw.name if fw else None,
                'version': fw.version if fw else None
            } if fw else None,
            'domain': {
                'id': str(dom.id) if dom else None,
                'code': dom.code if dom else None,
                'name': dom.name if dom else None
            } if dom else None,
            'category': {
                'id': str(cat.id) if cat else None,
                'code': cat.code if cat else None,
                'name': cat.name if cat else None
            } if cat else None,
            'subcategory': {
                'id': str(subcat.id),
                'code': subcat.code,
                'name': subcat.name
            }
        }


class ControlCreateSerializer(serializers.ModelSerializer):
    """Create new control"""
    
    class Meta:
        model = Control
        fields = [
            'subcategory', 'control_code', 'title', 'description',
            'objective', 'control_type', 'frequency', 'risk_level',
            'sort_order'
        ]
    
    def validate_control_code(self, value):
        """Ensure unique control code"""
        if Control.objects.filter(control_code=value).exists():
            raise serializers.ValidationError(
                f"Control with code '{value}' already exists"
            )
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


# ============================================================================
# DEEP NESTED SERIALIZER (For full framework export)
# ============================================================================

class ControlDeepSerializer(serializers.ModelSerializer):
    """Control with questions, evidence, and full hierarchy"""
    assessment_questions = AssessmentQuestionSerializer(many=True, read_only=True)
    evidence_requirements = EvidenceRequirementSerializer(many=True, read_only=True)
    hierarchy = serializers.SerializerMethodField()
    
    class Meta:
        model = Control
        fields = [
            'id', 'control_code', 'title', 'description', 'objective',
            'control_type', 'frequency', 'risk_level', 'sort_order',
            'assessment_questions', 'evidence_requirements',
            'hierarchy', 'is_active'
        ]
    
    def get_hierarchy(self, obj):
        """Get complete hierarchy path"""
        if not obj.subcategory:
            return None
        
        subcat = obj.subcategory
        cat = subcat.category if subcat else None
        dom = cat.domain if cat else None
        fw = dom.framework if dom else None
        
        return {
            'framework': {
                'id': str(fw.id) if fw else None,
                'name': fw.name if fw else None,
                'version': fw.version if fw else None
            } if fw else None,
            'domain': {
                'id': str(dom.id) if dom else None,
                'code': dom.code if dom else None,
                'name': dom.name if dom else None
            } if dom else None,
            'category': {
                'id': str(cat.id) if cat else None,
                'code': cat.code if cat else None,
                'name': cat.name if cat else None
            } if cat else None,
            'subcategory': {
                'id': str(subcat.id) if subcat else None,
                'code': subcat.code if subcat else None,
                'name': subcat.name if subcat else None
            }
        }


class SubcategoryDeepSerializer(serializers.ModelSerializer):
    """Subcategory with controls"""
    controls = ControlDeepSerializer(many=True, read_only=True)
    
    class Meta:
        model = Subcategory
        fields = ['id', 'code', 'name', 'description', 'sort_order', 'controls']


class CategoryDeepSerializer(serializers.ModelSerializer):
    """Category with subcategories"""
    subcategories = SubcategoryDeepSerializer(many=True, read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'code', 'name', 'description', 'sort_order', 'subcategories']


class DomainDeepSerializer(serializers.ModelSerializer):
    """Domain with full nested structure"""
    categories = CategoryDeepSerializer(many=True, read_only=True)
    framework_name = serializers.CharField(source='framework.name', read_only=True, allow_null=True)
    framework_version = serializers.CharField(source='framework.version', read_only=True, allow_null=True)
    
    class Meta:
        model = Domain
        fields = [
            'id', 'framework', 'framework_name', 'framework_version',
            'code', 'name', 'description', 'sort_order',
            'categories', 'is_active'
        ]


class FrameworkDeepSerializer(serializers.ModelSerializer):
    """Complete framework with all nested data"""
    category = FrameworkCategorySerializer(read_only=True)
    domains = DomainDeepSerializer(many=True, read_only=True)
    
    class Meta:
        model = Framework
        fields = [
            'id', 'name', 'full_name', 'description', 'version',
            'status', 'effective_date', 'category', 'domains'
        ]


# ============================================================================
# LINKING SERIALIZERS (For flexible linking/unlinking)
# ============================================================================

class LinkFrameworkSerializer(serializers.Serializer):
    """Link domain to framework"""
    framework_id = serializers.UUIDField(required=True)
    
    def validate_framework_id(self, value):
        if not Framework.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Framework not found or inactive")
        return value


class LinkDomainSerializer(serializers.Serializer):
    """Link category to domain"""
    domain_id = serializers.UUIDField(required=True)
    
    def validate_domain_id(self, value):
        if not Domain.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Domain not found or inactive")
        return value


class LinkCategorySerializer(serializers.Serializer):
    """Link subcategory to category"""
    category_id = serializers.UUIDField(required=True)
    
    def validate_category_id(self, value):
        if not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Category not found or inactive")
        return value


class LinkSubcategorySerializer(serializers.Serializer):
    """Link control to subcategory"""
    subcategory_id = serializers.UUIDField(required=True)
    
    def validate_subcategory_id(self, value):
        if not Subcategory.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Subcategory not found or inactive")
        return value
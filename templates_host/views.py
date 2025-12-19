"""
Framework Template API Views
SuperAdmin only - manages framework templates
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch
from django.db import IntegrityError

from .models import (
    Framework, FrameworkCategory, Domain, Category, Subcategory,
    Control, AssessmentQuestion, EvidenceRequirement
)
from .serializers import (
    FrameworkCategorySerializer,
    FrameworkBasicSerializer, FrameworkDetailSerializer,
    FrameworkCreateSerializer, FrameworkDeepSerializer,
    DomainBasicSerializer, DomainDetailSerializer, DomainCreateSerializer, DomainDeepSerializer,
    CategoryBasicSerializer, CategoryDetailSerializer, CategoryCreateSerializer,
    SubcategoryBasicSerializer, SubcategoryDetailSerializer, SubcategoryCreateSerializer,
    ControlBasicSerializer, ControlDetailSerializer, ControlCreateSerializer, ControlDeepSerializer,
    AssessmentQuestionSerializer, EvidenceRequirementSerializer,
    LinkFrameworkSerializer, LinkDomainSerializer, LinkCategorySerializer, LinkSubcategorySerializer
)
from .permissions import IsSuperAdminUser, IsAdminOrReadOnly


# ============================================================================
# FRAMEWORK CATEGORY VIEWS
# ============================================================================

class FrameworkCategoryViewSet(viewsets.ModelViewSet):
    """
    Framework categories (Financial, Security, Healthcare, etc.)
    
    GET /api/v1/templates/categories/
    POST /api/v1/templates/categories/
    """
    
    queryset = FrameworkCategory.objects.filter(is_active=True).order_by('sort_order')
    serializer_class = FrameworkCategorySerializer
    permission_classes = [IsSuperAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'sort_order']
    ordering = ['sort_order']


# ============================================================================
# FRAMEWORK VIEWS
# ============================================================================

class FrameworkViewSet(viewsets.ModelViewSet):
    """
    Compliance Framework Templates (SOX, ISO 27001, GDPR, etc.)
    
    SuperAdmin only - manages master templates
    
    GET /api/v1/templates/frameworks/
    GET /api/v1/templates/frameworks/{id}/?deep=true  # Full nested data
    POST /api/v1/templates/frameworks/
    PATCH /api/v1/templates/frameworks/{id}/
    DELETE /api/v1/templates/frameworks/{id}/
    """
    
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category']
    search_fields = ['name', 'full_name', 'description']
    ordering_fields = ['name', 'version', 'created_at']
    ordering = ['name', '-version']
    
    def get_queryset(self):
        """Optimize based on deep parameter"""
        queryset = Framework.objects.filter(is_active=True)
        
        # Check if deep nested data requested
        deep = self.request.query_params.get('deep') in ('1', 'true', 'True')
        
        if deep:
            # Optimize for deep serialization with prefetch
            controls_qs = Control.objects.filter(is_active=True).prefetch_related(
                'assessment_questions', 'evidence_requirements'
            ).order_by('sort_order')
            
            subcategories_qs = Subcategory.objects.filter(is_active=True).prefetch_related(
                Prefetch('controls', queryset=controls_qs)
            ).order_by('sort_order')
            
            categories_qs = Category.objects.filter(is_active=True).prefetch_related(
                Prefetch('subcategories', queryset=subcategories_qs)
            ).order_by('sort_order')
            
            domains_qs = Domain.objects.filter(is_active=True).prefetch_related(
                Prefetch('categories', queryset=categories_qs)
            ).order_by('sort_order')
            
            queryset = queryset.prefetch_related(
                Prefetch('domains', queryset=domains_qs),
                'category'
            )
        else:
            queryset = queryset.select_related('category')
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == 'create':
            return FrameworkCreateSerializer
        
        # Check for deep parameter (works for both list and retrieve)
        deep = self.request.query_params.get('deep') in ('1', 'true', 'True')
        if deep:
            return FrameworkDeepSerializer  # ← Use deep for list AND retrieve
        
        # Use basic for list without deep
        if self.action == 'list':
            return FrameworkBasicSerializer
        
        return FrameworkDetailSerializer

    
    @action(detail=True, methods=['get'])
    def domains(self, request, pk=None):
        """
        Get all domains for a framework
        
        GET /api/v1/templates/frameworks/{id}/domains/
        """
        framework = self.get_object()
        domains = framework.domains.filter(is_active=True).order_by('sort_order')
        serializer = DomainBasicSerializer(domains, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Get framework statistics
        
        GET /api/v1/templates/frameworks/{id}/stats/
        """
        framework = self.get_object()
        
        # Count hierarchy elements
        domains = framework.domains.filter(is_active=True)
        categories = Category.objects.filter(
            domain__framework=framework,
            is_active=True
        )
        subcategories = Subcategory.objects.filter(
            category__domain__framework=framework,
            is_active=True
        )
        controls = Control.objects.filter(
            subcategory__category__domain__framework=framework,
            is_active=True
        )
        
        # Count by control type
        control_types = {}
        for ct in ['PREVENTIVE', 'DETECTIVE', 'CORRECTIVE']:
            control_types[ct.lower()] = controls.filter(control_type=ct).count()
        
        # Count by risk level
        risk_levels = {}
        for rl in ['HIGH', 'MEDIUM', 'LOW']:
            risk_levels[rl.lower()] = controls.filter(risk_level=rl).count()
        
        return Response({
            'framework_id': str(framework.id),
            'framework_name': framework.name,
            'version': framework.version,
            'hierarchy': {
                'domains': domains.count(),
                'categories': categories.count(),
                'subcategories': subcategories.count(),
                'controls': controls.count()
            },
            'control_types': control_types,
            'risk_levels': risk_levels
        })
    
    @action(detail=True, methods=['get'])
    def validate(self, request, pk=None):
        """
        Validate framework completeness
        
        GET /api/v1/templates/frameworks/{id}/validate/
        """
        from .validators import validate_framework_completeness
        
        framework = self.get_object()
        validation_result = validate_framework_completeness(framework)
        
        return Response({
            'framework_id': str(framework.id),
            'framework_name': framework.name,
            'version': framework.version,
            **validation_result
        })

    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """
        Clone framework with new version
        
        POST /api/v1/templates/frameworks/{id}/clone/
        {
            "version": "2024",
            "name": "SOX_2024"
        }
        """
        framework = self.get_object()
        new_version = request.data.get('version')
        new_name = request.data.get('name', f"{framework.name}_COPY")
        
        if not new_version:
            return Response(
                {'error': 'Version is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new framework (just shell, not copying structure yet)
        new_framework = Framework.objects.create(
            name=new_name,
            full_name=f"{framework.full_name} (v{new_version})",
            description=framework.description,
            version=new_version,
            status='DRAFT',
            category=framework.category,
            created_by=request.user
        )
        
        return Response(
            FrameworkDetailSerializer(new_framework).data,
            status=status.HTTP_201_CREATED
        )


# ============================================================================
# DOMAIN VIEWS
# ============================================================================

class DomainViewSet(viewsets.ModelViewSet):
    """
    Framework Domains
    
    GET /api/v1/templates/domains/
    POST /api/v1/templates/domains/
    """
    
    queryset = Domain.objects.filter(is_active=True).select_related('framework')
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['framework', 'code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['framework', 'sort_order']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DomainCreateSerializer
        elif self.action == 'list':
            return DomainBasicSerializer
        return DomainDetailSerializer
    
    @action(detail=True, methods=['get'])
    def categories(self, request, pk=None):
        """Get categories for a domain"""
        domain = self.get_object()
        categories = domain.categories.filter(is_active=True).order_by('sort_order')
        serializer = CategoryBasicSerializer(categories, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        """Optimize based on deep parameter"""
        queryset = Domain.objects.filter(is_active=True).select_related('framework')
        
        # ✅ NEW: Support deep parameter
        if self.request.query_params.get('deep') in ('1', 'true', 'True'):
            queryset = queryset.prefetch_related(
                'categories__subcategories__controls__assessment_questions',
                'categories__subcategories__controls__evidence_requirements'
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == 'create':
            return DomainCreateSerializer
        elif self.action == 'list':
            return DomainBasicSerializer
        
        # ✅ NEW: Deep serializer support
        if self.request.query_params.get('deep') in ('1', 'true', 'True'):
            return DomainDeepSerializer
        
        return DomainDetailSerializer
    
    @action(detail=True, methods=['get'])
    def categories(self, request, pk=None):
        """Get categories for a domain"""
        domain = self.get_object()
        categories = domain.categories.filter(is_active=True).order_by('sort_order')
        serializer = CategoryBasicSerializer(categories, many=True)
        return Response(serializer.data)
    
    # ============================================================================
    # ✅ NEW: LINKING ACTIONS
    # ============================================================================
    
    @action(detail=True, methods=['post'])
    def link_framework(self, request, pk=None):
        """
        Link domain to framework
        
        POST /api/v1/templates/domains/{id}/link_framework/
        {
            "framework_id": "uuid..."
        }
        """
        domain = self.get_object()
        serializer = LinkFrameworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        framework_id = serializer.validated_data['framework_id']
        framework = Framework.objects.get(id=framework_id)
        
        # Check for duplicate code in framework
        existing = Domain.objects.filter(
            framework=framework,
            code=domain.code
        ).exclude(id=domain.id)
        
        if existing.exists():
            return Response({
                'error': f"Domain with code '{domain.code}' already exists in framework '{framework.name}'"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Link domain to framework
        domain.framework = framework
        domain.save(update_fields=['framework', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Domain "{domain.name}" linked to framework "{framework.name}"',
            'domain': DomainDetailSerializer(domain).data
        })
    
    @action(detail=True, methods=['post'])
    def unlink_framework(self, request, pk=None):
        """
        Unlink domain from framework
        
        POST /api/v1/templates/domains/{id}/unlink_framework/
        """
        domain = self.get_object()
        
        if not domain.framework:
            return Response({
                'error': 'Domain is not linked to any framework'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        framework_name = domain.framework.name
        domain.framework = None
        domain.save(update_fields=['framework', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Domain "{domain.name}" unlinked from framework "{framework_name}"',
            'domain': DomainDetailSerializer(domain).data
        })

# ============================================================================
# CATEGORY VIEWS
# ============================================================================

class CategoryViewSet(viewsets.ModelViewSet):
    """
    Framework Categories
    
    GET /api/v1/templates/categories/
    POST /api/v1/templates/categories/
    """
    
    queryset = Category.objects.filter(is_active=True).select_related('domain__framework')
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['domain', 'sort_order']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CategoryCreateSerializer
        elif self.action == 'list':
            return CategoryBasicSerializer
        return CategoryDetailSerializer
    

    
    @action(detail=True, methods=['get'])
    def subcategories(self, request, pk=None):
        """Get subcategories for a category"""
        category = self.get_object()
        subcategories = category.subcategories.filter(is_active=True).order_by('sort_order')
        serializer = SubcategoryBasicSerializer(subcategories, many=True)
        return Response(serializer.data)
    
    # ============================================================================
    # ✅ NEW: LINKING ACTIONS
    # ============================================================================
    
    @action(detail=True, methods=['post'])
    def link_domain(self, request, pk=None):
        """
        Link category to domain
        
        POST /api/v1/templates/categories/{id}/link_domain/
        {
            "domain_id": "uuid..."
        }
        """
        category = self.get_object()
        serializer = LinkDomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        domain_id = serializer.validated_data['domain_id']
        domain = Domain.objects.get(id=domain_id)
        
        # Check for duplicate code in domain
        existing = Category.objects.filter(
            domain=domain,
            code=category.code
        ).exclude(id=category.id)
        
        if existing.exists():
            return Response({
                'error': f"Category with code '{category.code}' already exists in domain '{domain.name}'"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Link category to domain
        category.domain = domain
        category.save(update_fields=['domain', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Category "{category.name}" linked to domain "{domain.name}"',
            'category': CategoryDetailSerializer(category).data
        })
    
    @action(detail=True, methods=['post'])
    def unlink_domain(self, request, pk=None):
        """
        Unlink category from domain
        
        POST /api/v1/templates/categories/{id}/unlink_domain/
        """
        category = self.get_object()
        
        if not category.domain:
            return Response({
                'error': 'Category is not linked to any domain'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        domain_name = category.domain.name
        category.domain = None
        category.save(update_fields=['domain', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Category "{category.name}" unlinked from domain "{domain_name}"',
            'category': CategoryDetailSerializer(category).data
        })


# ============================================================================
# SUBCATEGORY VIEWS
# ============================================================================

class SubcategoryViewSet(viewsets.ModelViewSet):
    """
    Framework Subcategories
    
    GET /api/v1/templates/subcategories/
    POST /api/v1/templates/subcategories/
    """
    
    queryset = Subcategory.objects.filter(is_active=True).select_related(
        'category__domain__framework'
    )
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['category', 'sort_order']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SubcategoryCreateSerializer
        elif self.action == 'list':
            return SubcategoryBasicSerializer
        return SubcategoryDetailSerializer
    
    @action(detail=True, methods=['get'])
    def controls(self, request, pk=None):
        """Get controls for a subcategory"""
        subcategory = self.get_object()
        controls = subcategory.controls.filter(is_active=True).order_by('sort_order')
        serializer = ControlBasicSerializer(controls, many=True)
        return Response(serializer.data)

    
    # ============================================================================
    # ✅ NEW: LINKING ACTIONS
    # ============================================================================
    
    @action(detail=True, methods=['post'])
    def link_category(self, request, pk=None):
        """
        Link subcategory to category
        
        POST /api/v1/templates/subcategories/{id}/link_category/
        {
            "category_id": "uuid..."
        }
        """
        subcategory = self.get_object()
        serializer = LinkCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        category_id = serializer.validated_data['category_id']
        category = Category.objects.get(id=category_id)
        
        # Check for duplicate code in category
        existing = Subcategory.objects.filter(
            category=category,
            code=subcategory.code
        ).exclude(id=subcategory.id)
        
        if existing.exists():
            return Response({
                'error': f"Subcategory with code '{subcategory.code}' already exists in category '{category.name}'"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Link subcategory to category
        subcategory.category = category
        subcategory.save(update_fields=['category', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Subcategory "{subcategory.name}" linked to category "{category.name}"',
            'subcategory': SubcategoryDetailSerializer(subcategory).data
        })
    
    @action(detail=True, methods=['post'])
    def unlink_category(self, request, pk=None):
        """
        Unlink subcategory from category
        
        POST /api/v1/templates/subcategories/{id}/unlink_category/
        """
        subcategory = self.get_object()
        
        if not subcategory.category:
            return Response({
                'error': 'Subcategory is not linked to any category'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        category_name = subcategory.category.name
        subcategory.category = None
        subcategory.save(update_fields=['category', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Subcategory "{subcategory.name}" unlinked from category "{category_name}"',
            'subcategory': SubcategoryDetailSerializer(subcategory).data
        })
# ============================================================================
# CONTROL VIEWS
# ============================================================================

class ControlViewSet(viewsets.ModelViewSet):
    """
    Compliance Controls
    
    GET /api/v1/templates/controls/
    POST /api/v1/templates/controls/
    """
    
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['subcategory', 'control_type', 'frequency', 'risk_level']
    search_fields = ['control_code', 'title', 'description', 'objective']
    ordering_fields = ['control_code', 'title', 'sort_order', 'created_at']
    ordering = ['subcategory', 'sort_order']
    
    def get_queryset(self):
        """Optimize queries with deep support"""
        queryset = Control.objects.filter(is_active=True).select_related(
            'subcategory',
            'subcategory__category',
            'subcategory__category__domain',
            'subcategory__category__domain__framework'
        )
        
        # ✅ NEW: Always prefetch for detail views
        if self.action in ['retrieve', 'list'] or self.request.query_params.get('deep') in ('1', 'true', 'True'):
            queryset = queryset.prefetch_related(
                'assessment_questions',
                'evidence_requirements'
            )
        
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer"""
        if self.action == 'create':
            return ControlCreateSerializer
        elif self.action == 'list':
            return ControlBasicSerializer
        
        # ✅ NEW: Deep serializer support
        if self.request.query_params.get('deep') in ('1', 'true', 'True'):
            return ControlDeepSerializer
        
        return ControlDetailSerializer   


    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced control search
        
        GET /api/v1/templates/controls/search/?q=password&framework=SOX&risk_level=HIGH
        """
        query = request.GET.get('q', '')
        framework = request.GET.get('framework', '')
        control_type = request.GET.get('control_type', '')
        risk_level = request.GET.get('risk_level', '')
        
        queryset = self.get_queryset()
        
        if query:
            queryset = queryset.filter(
                Q(control_code__icontains=query) |
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(objective__icontains=query)
            )
        
        if framework:
            queryset = queryset.filter(
                subcategory__category__domain__framework__name__iexact=framework
            )
        
        if control_type:
            queryset = queryset.filter(control_type=control_type)
        
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        serializer = ControlBasicSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get assessment questions"""
        control = self.get_object()
        questions = control.assessment_questions.filter(is_active=True).order_by('sort_order')
        serializer = AssessmentQuestionSerializer(questions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def evidence(self, request, pk=None):
        """Get evidence requirements"""
        control = self.get_object()
        evidence = control.evidence_requirements.filter(is_active=True).order_by('sort_order')
        serializer = EvidenceRequirementSerializer(evidence, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_question(self, request, pk=None):
        """
        Add assessment question to control
        
        POST /api/v1/templates/controls/{id}/add_question/
        {
            "question_type": "YES_NO",
            "question": "Is password complexity enforced?",
            "is_mandatory": true
        }
        """
        control = self.get_object()
        data = request.data.copy()
        data['control'] = control.id
        
        serializer = AssessmentQuestionSerializer(data=data)
        if serializer.is_valid():
            serializer.save(control=control)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_evidence(self, request, pk=None):
        """
        Add evidence requirement to control
        
        POST /api/v1/templates/controls/{id}/add_evidence/
        {
            "title": "Password Policy Document",
            "evidence_type": "DOCUMENT",
            "is_mandatory": true
        }
        """
        control = self.get_object()
        data = request.data.copy()
        data['control'] = control.id
        
        serializer = EvidenceRequirementSerializer(data=data)
        if serializer.is_valid():
            serializer.save(control=control)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# ASSESSMENT QUESTION VIEWS
# ============================================================================

class AssessmentQuestionViewSet(viewsets.ModelViewSet):
    """
    Assessment Questions
    
    GET /api/v1/templates/questions/
    POST /api/v1/templates/questions/
    """
    
    queryset = AssessmentQuestion.objects.filter(is_active=True).select_related('control')
    serializer_class = AssessmentQuestionSerializer
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['control', 'question_type', 'is_mandatory']
    search_fields = ['question']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['control', 'sort_order']
    
    def perform_create(self, serializer):
        """Ensure control is provided"""
        control_id = self.request.data.get('control')
        if not control_id:
            raise ValidationError({'control': 'This field is required'})
        
        try:
            control = Control.objects.get(pk=control_id, is_active=True)
            serializer.save(control=control)
        except Control.DoesNotExist:
            raise ValidationError({'control': 'Invalid control ID'})


# ============================================================================
# EVIDENCE REQUIREMENT VIEWS
# ============================================================================

class EvidenceRequirementViewSet(viewsets.ModelViewSet):
    """
    Evidence Requirements
    
    GET /api/v1/templates/evidence/
    POST /api/v1/templates/evidence/
    """
    
    queryset = EvidenceRequirement.objects.filter(is_active=True).select_related('control')
    serializer_class = EvidenceRequirementSerializer
    permission_classes = [IsSuperAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['control', 'evidence_type', 'is_mandatory']
    search_fields = ['title', 'description']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['control', 'sort_order']
    
    def perform_create(self, serializer):
        """Ensure control is provided"""
        control_id = self.request.data.get('control')
        if not control_id:
            raise ValidationError({'control': 'This field is required'})
        
        try:
            control = Control.objects.get(pk=control_id, is_active=True)
            serializer.save(control=control)
        except Control.DoesNotExist:
            raise ValidationError({'control': 'Invalid control ID'})
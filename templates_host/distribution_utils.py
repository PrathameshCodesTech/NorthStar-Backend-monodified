"""
Framework Distribution Utilities
Handles copying framework templates to tenant schemas/databases

This is the CORE functionality that enables:
1. Tenant subscription to frameworks
2. Framework template → Company framework conversion
3. Schema/Database routing based on isolation mode
"""

from django.db import connections, transaction
from django.utils import timezone
from django.contrib.auth.models import User
import logging

from .models import (
    Framework, Domain, Category, Subcategory,
    Control, AssessmentQuestion, EvidenceRequirement
)
from company_compliance.models import (
    CompanyFramework, CompanyDomain, CompanyCategory, CompanySubcategory,
    CompanyControl, CompanyAssessmentQuestion, CompanyEvidenceRequirement
)
from tenant_management.models import TenantDatabaseInfo

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN DISTRIBUTION FUNCTION
# ============================================================================

def copy_framework_to_tenant(tenant, framework_id, customization_level='CONTROL_LEVEL'):
    """
    Copy framework template to tenant's schema/database
    
    Args:
        tenant: TenantDatabaseInfo instance
        framework_id: UUID of framework template
        customization_level: VIEW_ONLY, CONTROL_LEVEL, or FULL
    
    Returns:
        dict: {
            'success': bool,
            'framework_id': UUID,
            'stats': {...},
            'error': str (if failed)
        }
    """
    
    try:
        # Validate framework exists
        try:
            framework = Framework.objects.get(id=framework_id, is_active=True)
        except Framework.DoesNotExist:
            return {
                'success': False,
                'error': f'Framework {framework_id} not found'
            }
        
        # Validate tenant
        if not tenant or not tenant.is_active:
            return {
                'success': False,
                'error': 'Invalid or inactive tenant'
            }
        
        # Determine database connection name
        connection_name = get_tenant_connection_name(tenant)
        
        logger.info(
            f"Starting framework distribution: {framework.name} → {tenant.tenant_slug} "
            f"(connection: {connection_name}, mode: {tenant.isolation_mode})"
        )
        
        # ✅ Set search_path for SCHEMA mode BEFORE transaction
        if tenant.isolation_mode == 'SCHEMA':
            set_schema_search_path(connection_name, tenant.schema_name)
            logger.info(f"Search path set to: {tenant.schema_name}")
        
        # Copy framework with transaction
        with transaction.atomic(using=connection_name):
            stats = _copy_framework_structure(
                framework=framework,
                tenant=tenant,
                connection_name=connection_name,
                customization_level=customization_level
            )

        
        logger.info(
            f"Framework distribution completed: {framework.name} → {tenant.tenant_slug}. "
            f"Stats: {stats}"
        )
        
        return {
            'success': True,
            'framework_id': str(framework.id),
            'framework_name': framework.name,
            'tenant_slug': tenant.tenant_slug,
            'stats': stats
        }
    
    except Exception as e:
        logger.error(
            f"Framework distribution failed: {framework_id} → {tenant.tenant_slug if tenant else 'unknown'}. "
            f"Error: {str(e)}",
            exc_info=True
        )
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_tenant_connection_name(tenant):
    """
    Get Django database connection name for tenant
    
    Args:
        tenant: TenantDatabaseInfo instance
    
    Returns:
        str: Database connection name (registered connection with search_path)
    """
    if tenant.isolation_mode == 'DATABASE':
        # Dedicated database
        return f"{tenant.tenant_slug}_compliance_db"
    else:
        # Schema isolation - use the registered connection with search_path
        return f"{tenant.tenant_slug}_compliance_db"
    

def set_schema_search_path(connection_name, schema_name):
    """
    Set search_path for schema isolation mode
    Must be called before any DB operations in SCHEMA mode
    """
    from django.db import connections
    
    try:
        with connections[connection_name].cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema_name}, public;")
            logger.debug(f"Set search_path to {schema_name}")
    except Exception as e:
        logger.error(f"Failed to set search_path: {e}")
        raise


def _copy_framework_structure(framework, tenant, connection_name, customization_level):
    """
    Copy complete framework structure to tenant
    
    Returns:
        dict: Statistics about copied items
    """
    
    stats = {
        'frameworks': 0,
        'domains': 0,
        'categories': 0,
        'subcategories': 0,
        'controls': 0,
        'questions': 0,
        'evidence': 0
    }
    
    # Step 1: Create CompanyFramework
    company_framework = _copy_framework(
        framework=framework,
        tenant=tenant,
        connection_name=connection_name,
        customization_level=customization_level
    )
    stats['frameworks'] = 1
    
    # Step 2: Copy Domains
    domains = framework.domains.filter(is_active=True).order_by('sort_order')
    domain_map = {}  # template_id → company_id
    
    for domain in domains:
        company_domain = _copy_domain(
            domain=domain,
            company_framework=company_framework,
            connection_name=connection_name
        )
        domain_map[domain.id] = company_domain.id
        stats['domains'] += 1
        
        # Step 3: Copy Categories
        categories = domain.categories.filter(is_active=True).order_by('sort_order')
        category_map = {}
        
        for category in categories:
            company_category = _copy_category(
                category=category,
                company_domain=company_domain,
                connection_name=connection_name
            )
            category_map[category.id] = company_category.id
            stats['categories'] += 1
            
            # Step 4: Copy Subcategories
            subcategories = category.subcategories.filter(is_active=True).order_by('sort_order')
            subcategory_map = {}
            
            for subcategory in subcategories:
                company_subcategory = _copy_subcategory(
                    subcategory=subcategory,
                    company_category=company_category,
                    connection_name=connection_name
                )
                subcategory_map[subcategory.id] = company_subcategory.id
                stats['subcategories'] += 1
                
                # Step 5: Copy Controls
                controls = subcategory.controls.filter(is_active=True).order_by('sort_order')
                
                for control in controls:
                    company_control = _copy_control(
                        control=control,
                        company_subcategory=company_subcategory,
                        connection_name=connection_name,
                        customization_level=customization_level
                    )
                    stats['controls'] += 1
                    
                    # Step 6: Copy Assessment Questions
                    questions = control.assessment_questions.filter(is_active=True).order_by('sort_order')
                    for question in questions:
                        _copy_assessment_question(
                            question=question,
                            company_control=company_control,
                            connection_name=connection_name
                        )
                        stats['questions'] += 1
                    
                    # Step 7: Copy Evidence Requirements
                    evidence_reqs = control.evidence_requirements.filter(is_active=True).order_by('sort_order')
                    for evidence in evidence_reqs:
                        _copy_evidence_requirement(
                            evidence=evidence,
                            company_control=company_control,
                            connection_name=connection_name
                        )
                        stats['evidence'] += 1
    
    return stats


def _copy_framework(framework, tenant, connection_name, customization_level):
    """Copy Framework → CompanyFramework"""
    
    company_framework = CompanyFramework(
        # Template reference
        template_framework_id=framework.id,
        is_template_synced=True,
        
        # Basic info
        name=framework.name,
        full_name=framework.full_name,
        description=framework.description,
        version=framework.version,
        effective_date=framework.effective_date,
        status=framework.status,
        
        # Customization settings
        customization_level=customization_level,
        is_customized=False,
        
        
        # Timestamps
        subscribed_at=timezone.now(),
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_framework.save(using=connection_name)
    
    logger.debug(f"Created CompanyFramework: {company_framework.name} (ID: {company_framework.id})")
    
    return company_framework


def _copy_domain(domain, company_framework, connection_name):
    """Copy Domain → CompanyDomain"""
    
    company_domain = CompanyDomain(
        # Template reference
        template_domain_id=domain.id,
        
        # Hierarchy
        framework=company_framework,
        
        # Basic info
        code=domain.code,
        name=domain.name,
        description=domain.description,
        sort_order=domain.sort_order,
        
        # Customization
        is_custom=False,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_domain.save(using=connection_name)
    
    return company_domain


def _copy_category(category, company_domain, connection_name):
    """Copy Category → CompanyCategory"""
    
    company_category = CompanyCategory(
        # Template reference
        template_category_id=category.id,
        
        # Hierarchy
        domain=company_domain,
        
        # Basic info
        code=category.code,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        
        # Customization
        is_custom=False,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_category.save(using=connection_name)
    
    return company_category


def _copy_subcategory(subcategory, company_category, connection_name):
    """Copy Subcategory → CompanySubcategory"""
    
    company_subcategory = CompanySubcategory(
        # Template reference
        template_subcategory_id=subcategory.id,
        
        # Hierarchy
        category=company_category,
        
        # Basic info
        code=subcategory.code,
        name=subcategory.name,
        description=subcategory.description,
        sort_order=subcategory.sort_order,
        
        # Customization
        is_custom=False,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_subcategory.save(using=connection_name)
    
    return company_subcategory

def _copy_control(control, company_subcategory, connection_name, customization_level):
    """Copy Control → CompanyControl"""
    
    can_customize = (customization_level in ['CONTROL_LEVEL', 'FULL'])
    
    company_control = CompanyControl(
        # Template reference
        template_control_id=control.id,
        
        # Hierarchy
        subcategory=company_subcategory,
        
        # Basic info
        control_code=control.control_code,
        title=control.title,
        description=control.description,
        objective=control.objective,
        
        # Classification
        control_type=control.control_type,
        frequency=control.frequency,
        risk_level=control.risk_level,
        sort_order=control.sort_order,
        
        # Customization
        can_customize=can_customize,
        is_customized=False,
        custom_title=None,
        custom_description=None,
        custom_objective=None,
        custom_procedures=None,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_control.save(using=connection_name)
    
    return company_control



def _copy_assessment_question(question, company_control, connection_name):
    """Copy AssessmentQuestion → CompanyAssessmentQuestion"""
    
    company_question = CompanyAssessmentQuestion(
        # Template reference
        template_question_id=question.id,
        
        # Hierarchy
        control=company_control,
        
        # Basic info
        question_type=question.question_type,
        question=question.question,
        # ✅ REMOVED: guidance field (doesn't exist in template)
        options=getattr(question, 'options', None),  # ✅ Copy options if exists
        is_mandatory=question.is_mandatory,
        sort_order=question.sort_order,
        
        # Customization
        is_custom=False,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_question.save(using=connection_name)
    
    return company_question


def _copy_evidence_requirement(evidence, company_control, connection_name):
    """Copy EvidenceRequirement → CompanyEvidenceRequirement"""
    
    company_evidence = CompanyEvidenceRequirement(
        # Template reference
        template_evidence_id=evidence.id,
        
        # Hierarchy
        control=company_control,
        
        # Basic info
        title=evidence.title,
        description=evidence.description,
        evidence_type=evidence.evidence_type,
        file_format=evidence.file_format,
        is_mandatory=evidence.is_mandatory,
        sort_order=evidence.sort_order,
        
        # Customization
        is_custom=False,
        
        # Timestamps
        created_at=timezone.now(),
        updated_at=timezone.now(),
        is_active=True
    )
    
    company_evidence.save(using=connection_name)
    
    return company_evidence


# ============================================================================
# FRAMEWORK SYNC FUNCTIONS (For future updates)
# ============================================================================

def sync_framework_updates(tenant, framework_id):
    """
    Sync framework template updates to tenant
    (For future use when templates are updated)
    
    Args:
        tenant: TenantDatabaseInfo instance
        framework_id: UUID of framework template
    
    Returns:
        dict: Sync results
    """
    
    # TODO: Implement framework update sync
    # This will be used when framework templates are updated
    # and we need to push updates to tenants
    
    return {
        'success': False,
        'error': 'Framework sync not yet implemented'
    }


def check_framework_version(tenant, framework_id):
    """
    Check if tenant's framework is up-to-date with template
    
    Args:
        tenant: TenantDatabaseInfo instance
        framework_id: UUID of framework template
    
    Returns:
        dict: Version comparison
    """
    
    try:
        # Get template framework
        template_framework = Framework.objects.get(id=framework_id)
        
        # Get company framework
        connection_name = get_tenant_connection_name(tenant)
        company_framework = CompanyFramework.objects.using(connection_name).get(
            template_framework_id=framework_id
        )
        
        is_outdated = (company_framework.version != template_framework.version)
        
        return {
            'success': True,
            'template_version': template_framework.version,
            'company_version': company_framework.version,
            'is_outdated': is_outdated,
            'is_synced': company_framework.is_template_synced
        }
    
    except (Framework.DoesNotExist, CompanyFramework.DoesNotExist) as e:
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# BULK DISTRIBUTION FUNCTIONS
# ============================================================================

def distribute_framework_to_multiple_tenants(framework_id, tenant_slugs, customization_level='CONTROL_LEVEL'):
    """
    Distribute framework to multiple tenants at once
    (Useful for SuperAdmin bulk operations)
    
    Args:
        framework_id: UUID of framework template
        tenant_slugs: List of tenant slugs
        customization_level: Customization level for all tenants
    
    Returns:
        dict: Results for each tenant
    """
    
    results = {
        'success': [],
        'failed': [],
        'total': len(tenant_slugs)
    }
    
    for tenant_slug in tenant_slugs:
        try:
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            result = copy_framework_to_tenant(
                tenant=tenant,
                framework_id=framework_id,
                customization_level=customization_level
            )
            
            if result['success']:
                results['success'].append({
                    'tenant_slug': tenant_slug,
                    'stats': result['stats']
                })
            else:
                results['failed'].append({
                    'tenant_slug': tenant_slug,
                    'error': result['error']
                })
        
        except TenantDatabaseInfo.DoesNotExist:
            results['failed'].append({
                'tenant_slug': tenant_slug,
                'error': 'Tenant not found'
            })
        except Exception as e:
            results['failed'].append({
                'tenant_slug': tenant_slug,
                'error': str(e)
            })
    
    return results


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_framework_distribution(tenant, framework_id):
    """
    Validate that framework was distributed correctly
    
    Args:
        tenant: TenantDatabaseInfo instance
        framework_id: UUID of framework template
    
    Returns:
        dict: Validation results
    """
    
    try:
        connection_name = get_tenant_connection_name(tenant)
        
        # Check framework exists
        company_framework = CompanyFramework.objects.using(connection_name).get(
            template_framework_id=framework_id
        )
        
        # Count all elements
        domain_count = CompanyDomain.objects.using(connection_name).filter(
            framework=company_framework,
            is_active=True
        ).count()
        
        category_count = CompanyCategory.objects.using(connection_name).filter(
            domain__framework=company_framework,
            is_active=True
        ).count()
        
        subcategory_count = CompanySubcategory.objects.using(connection_name).filter(
            category__domain__framework=company_framework,
            is_active=True
        ).count()
        
        control_count = CompanyControl.objects.using(connection_name).filter(
            subcategory__category__domain__framework=company_framework,
            is_active=True
        ).count()
        
        return {
            'success': True,
            'framework_id': str(company_framework.id),
            'framework_name': company_framework.name,
            'counts': {
                'domains': domain_count,
                'categories': category_count,
                'subcategories': subcategory_count,
                'controls': control_count
            },
            'is_valid': (domain_count > 0 and control_count > 0)
        }
    
    except CompanyFramework.DoesNotExist:
        return {
            'success': False,
            'error': 'Framework not found in tenant database'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
"""
Validation utilities for framework templates
"""

from .models import Framework, Domain, Category, Subcategory, Control


def validate_framework_completeness(framework):
    """
    Check if framework is complete for distribution
    
    Returns:
        dict: {
            'is_complete': bool,
            'is_distributable': bool,
            'issues': list,
            'warnings': list,
            'stats': dict
        }
    """
    issues = []
    warnings = []
    
    # Check domains
    domains = framework.domains.filter(is_active=True)
    domain_count = domains.count()
    
    if domain_count == 0:
        issues.append("Framework has no domains")
    
    # Check categories
    total_categories = 0
    total_subcategories = 0
    total_controls = 0
    
    for domain in domains:
        categories = domain.categories.filter(is_active=True)
        category_count = categories.count()
        total_categories += category_count
        
        if category_count == 0:
            issues.append(f"Domain '{domain.code}' has no categories")
        
        for category in categories:
            subcategories = category.subcategories.filter(is_active=True)
            subcategory_count = subcategories.count()
            total_subcategories += subcategory_count
            
            if subcategory_count == 0:
                warnings.append(f"Category '{category.code}' has no subcategories")
            
            for subcategory in subcategories:
                controls = subcategory.controls.filter(is_active=True)
                control_count = controls.count()
                total_controls += control_count
                
                if control_count == 0:
                    warnings.append(f"Subcategory '{subcategory.code}' has no controls")
    
    # Overall validation
    is_complete = (
        domain_count > 0 and
        total_categories > 0 and
        total_subcategories > 0 and
        total_controls > 0
    )
    
    # Distributable = complete with no blocking issues
    is_distributable = is_complete and len(issues) == 0
    
    return {
        'is_complete': is_complete,
        'is_distributable': is_distributable,
        'issues': issues,
        'warnings': warnings,
        'stats': {
            'domains': domain_count,
            'categories': total_categories,
            'subcategories': total_subcategories,
            'controls': total_controls
        }
    }


def get_orphaned_items():
    """
    Find all orphaned template items (not linked to parents)
    
    Returns:
        dict: {
            'domains': QuerySet,
            'categories': QuerySet,
            'subcategories': QuerySet,
            'count': int
        }
    """
    orphaned_domains = Domain.objects.filter(framework__isnull=True, is_active=True)
    orphaned_categories = Category.objects.filter(domain__isnull=True, is_active=True)
    orphaned_subcategories = Subcategory.objects.filter(category__isnull=True, is_active=True)
    
    return {
        'domains': orphaned_domains,
        'categories': orphaned_categories,
        'subcategories': orphaned_subcategories,
        'count': (
            orphaned_domains.count() +
            orphaned_categories.count() +
            orphaned_subcategories.count()
        )
    }


def validate_hierarchy_path(item):
    """
    Validate complete hierarchy path for any item
    
    Args:
        item: Domain, Category, Subcategory, or Control instance
        
    Returns:
        dict: {
            'is_valid': bool,
            'missing_links': list,
            'path': dict
        }
    """
    from .models import Domain, Category, Subcategory, Control
    
    missing_links = []
    path = {}
    
    if isinstance(item, Control):
        path['control'] = str(item.id)
        if not item.subcategory:
            missing_links.append('subcategory')
            return {'is_valid': False, 'missing_links': missing_links, 'path': path}
        item = item.subcategory
    
    if isinstance(item, Subcategory):
        path['subcategory'] = str(item.id)
        if not item.category:
            missing_links.append('category')
            return {'is_valid': False, 'missing_links': missing_links, 'path': path}
        item = item.category
    
    if isinstance(item, Category):
        path['category'] = str(item.id)
        if not item.domain:
            missing_links.append('domain')
            return {'is_valid': False, 'missing_links': missing_links, 'path': path}
        item = item.domain
    
    if isinstance(item, Domain):
        path['domain'] = str(item.id)
        if not item.framework:
            missing_links.append('framework')
            return {'is_valid': False, 'missing_links': missing_links, 'path': path}
        path['framework'] = str(item.framework.id)
    
    return {
        'is_valid': len(missing_links) == 0,
        'missing_links': missing_links,
        'path': path
    }
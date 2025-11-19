"""
Validators for tenant management
Ensures tenant slugs are valid and safe
"""

import re
from django.core.exceptions import ValidationError


# Reserved slugs that cannot be used as tenant identifiers
RESERVED_TENANT_SLUGS = {
    # PostgreSQL reserved
    "postgres", "template0", "template1",
    
    # Common system names
    "admin", "default", "public", "master", "root", "system",
    
    # Application reserved
    "api", "www", "app", "web", "staging", "production", "dev",
    
    # Django reserved
    "static", "media", "admin", "accounts",
    
    # Security
    "test", "demo", "example", "sample"
}


# Slug must be: 3-50 chars, lowercase letters, numbers, hyphens only
SLUG_REGEX = r'^[a-z0-9-]{3,50}$'


def validate_and_normalize_slug(raw_slug: str) -> str:
    """
    Validate and normalize tenant slug
    
    Rules:
    - 3-50 characters
    - Lowercase letters, numbers, hyphens only
    - No underscores or spaces
    - Not in reserved list
    
    Args:
        raw_slug: Raw slug input from user
        
    Returns:
        Normalized slug (lowercase, trimmed)
        
    Raises:
        ValidationError: If slug is invalid
    """
    
    # Check if slug provided
    if raw_slug is None or raw_slug == '':
        raise ValidationError("tenant_slug is required")
    
    # Normalize: lowercase and trim
    slug = raw_slug.strip().lower()
    
    # Check for underscores or spaces (common mistake)
    if "_" in slug or " " in slug:
        raise ValidationError(
            "tenant_slug cannot contain underscores or spaces. Use hyphens instead."
        )
    
    # Check if reserved
    if slug in RESERVED_TENANT_SLUGS:
        raise ValidationError(
            f'tenant_slug "{slug}" is reserved. Please choose a different name.'
        )
    
    # Check format with regex
    if not re.fullmatch(SLUG_REGEX, slug):
        raise ValidationError(
            "tenant_slug must be 3-50 characters long and contain only "
            "lowercase letters (a-z), numbers (0-9), and hyphens (-)."
        )
    
    # Additional checks
    if slug.startswith('-') or slug.endswith('-'):
        raise ValidationError(
            "tenant_slug cannot start or end with a hyphen."
        )
    
    if '--' in slug:
        raise ValidationError(
            "tenant_slug cannot contain consecutive hyphens."
        )
    
    return slug


def validate_company_name(name: str) -> str:
    """
    Validate company name
    
    Rules:
    - 2-200 characters
    - No HTML/script tags
    - No special characters that could cause issues
    
    Args:
        name: Company name
        
    Returns:
        Cleaned name
        
    Raises:
        ValidationError: If name is invalid
    """
    
    if not name or not name.strip():
        raise ValidationError("company_name is required")
    
    cleaned = name.strip()
    
    # Length check
    if len(cleaned) < 2:
        raise ValidationError("company_name must be at least 2 characters")
    
    if len(cleaned) > 200:
        raise ValidationError("company_name must be 200 characters or less")
    
    # Check for dangerous characters
    dangerous_chars = '<>"\'&;'
    if any(char in cleaned for char in dangerous_chars):
        raise ValidationError(
            f"company_name contains invalid characters: {dangerous_chars}"
        )
    
    # Check for script tags
    if '<script' in cleaned.lower() or 'javascript:' in cleaned.lower():
        raise ValidationError("company_name contains potentially dangerous content")
    
    return cleaned


def validate_email(email: str) -> str:
    """
    Validate email address
    
    Args:
        email: Email address
        
    Returns:
        Lowercase email
        
    Raises:
        ValidationError: If email is invalid
    """
    from django.core.validators import validate_email as django_validate_email
    
    if not email or not email.strip():
        raise ValidationError("email is required")
    
    email = email.strip().lower()
    
    try:
        django_validate_email(email)
    except Exception:
        raise ValidationError(f"Invalid email address: {email}")
    
    return email
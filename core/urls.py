"""
Main URL Configuration - Vibe Connect Compliance Platform
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


# ============================================================================
# HEALTH CHECK FUNCTIONS
# ============================================================================

def health_check(request):
    return JsonResponse({
        'status': 'healthy',
        'service': 'vibe_connect_compliance_platform',
        'version': '1.0.0'
    })


def check_database_health(request):
    health_status = {'status': 'healthy', 'databases': {}}
    for db_name in connections.databases.keys():
        try:
            connection = connections[db_name]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['databases'][db_name] = 'healthy'
        except Exception as e:
            health_status['databases'][db_name] = {'status': 'error', 'error': str(e)}
            health_status['status'] = 'degraded'
    return JsonResponse(health_status, status=200 if health_status['status'] == 'healthy' else 503)


# ============================================================================
# GENERATE TENANT ADMIN PATTERNS
# ============================================================================

def get_tenant_admin_urls():
    """Generate URLConf patterns for all active tenants"""
    tenant_urls = []
    
    try:
        from tenant_management.models import TenantDatabaseInfo
        from company_compliance.tenant_admin import create_tenant_admin_site
        
        tenants = TenantDatabaseInfo.objects.filter(
            is_active=True,
            provisioning_status='ACTIVE'
        ).only('tenant_slug')
        
        print(f"\n{'='*70}")
        print(f"🔧 CREATING TENANT ADMIN URLs")
        print(f"{'='*70}")
        print(f"ℹ️  Found {tenants.count()} active tenant(s)")
        
        for tenant in tenants:
            tenant_admin_site = create_tenant_admin_site(tenant.tenant_slug)
            
            # Unpack the 3-tuple from admin site
            # admin_site.urls returns (urlpatterns, app_name, namespace)
            url_patterns, app_name, namespace = tenant_admin_site.urls
            
            # Create the path with proper namespace
            tenant_urls.append(
                path(
                    f'admin/tenant/{tenant.tenant_slug}/admin/',
                    include((url_patterns, app_name), namespace=namespace)
                )
            )
            
            print(f"✅ Registered: /admin/tenant/{tenant.tenant_slug}/admin/")
        
        print(f"{'='*70}\n")
        
    except Exception as e:
        import sys
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            print(f"⚠️  Could not create tenant admin URLs: {e}")
            import traceback
            traceback.print_exc()
    
    return tenant_urls


# ============================================================================
# URL PATTERNS
# ============================================================================

urlpatterns = [
    # Tenant admin list
    path('admin/tenant/', include('company_compliance.tenant_admin_urls')),
]

# Add tenant-specific admin patterns
urlpatterns += get_tenant_admin_urls()

# Continue with other URLs
urlpatterns += [
    # Main admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('api/auth/', include([
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    ])),
    
    # APIs
    path('api/v2/admin/', include('tenant_management.urls')),
    path('api/v2/', include('user_management.urls')),
    path('api/v1/templates/', include('templates_host.urls')),
    path('api/v1/company/', include('company_compliance.urls')),
    path('api/ai/', include('ai_reports.urls')),  
    
    # Health checks
    path('health/', health_check, name='health_check'),
    path('health/db/', check_database_health, name='database_health'),
]


# ============================================================================
# STATIC & MEDIA FILES
# ============================================================================

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# ============================================================================
# ADMIN CUSTOMIZATION
# ============================================================================

admin.site.site_header = "Vibe Connect - Compliance Platform"
admin.site.site_title = "Vibe Connect Admin"
admin.site.index_title = "Welcome to Compliance Platform Administration"
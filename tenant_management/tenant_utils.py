"""
Tenant Database Management Utilities - MONOLITH VERSION
Provisions tenant schemas/databases and runs migrations
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.core.cache import cache
from psycopg2 import sql
import secrets
import string
import logging
from django.utils import timezone
from datetime import timedelta
from django.apps import apps  


from .models import TenantDatabaseInfo

logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = 1800  # 30 minutes



def create_postgresql_schema(schema_name, db_name='main_compliance_system_db'):
    """
    Create PostgreSQL schema (SCHEMA isolation mode)
    Used for Basic/Professional plans
    """
    conn = psycopg2.connect(
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        database=db_name
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        # Check if schema exists
        cursor.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name=%s;", (schema_name,))
        schema_exists = cursor.fetchone() is not None

        if not schema_exists:
            cursor.execute(
                sql.SQL("CREATE SCHEMA {}")
                .format(sql.Identifier(schema_name))
            )
            logger.info(f"[SUCCESS] Created schema: {schema_name}")
        else:
            logger.info(f"[UPDATE] Schema already exists: {schema_name}")

        # Grant privileges
        cursor.execute(
            sql.SQL("GRANT ALL ON SCHEMA {} TO {}")
            .format(
                sql.Identifier(schema_name),
                sql.Identifier(settings.DATABASES['default']['USER'])
            )
        )
        logger.info(f"[SUCCESS] Granted privileges on schema: {schema_name}")

    except Exception as e:
        logger.error(f"[ERROR] Error creating schema: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def add_tenant_database_to_django(tenant_info):
    """
    Register tenant schema in Django connections
    SCHEMA mode only: Uses search_path to route to tenant schema
    """
    connection_name = f"{tenant_info.tenant_slug}_compliance_db"
    
    # Check if already registered
    if connection_name in connections.databases:
        logger.info(f"[UPDATE] Connection {connection_name} already registered")
        return connection_name
    
    default_db = settings.DATABASES['default'].copy()
    
    # SCHEMA mode: Same database, different schema via search_path
    db_config = {
        **default_db,
        'NAME': 'main_compliance_system_db',  # Shared database
        'OPTIONS': {
            'options': f'-c search_path={tenant_info.schema_name},public'
        },
        'CONN_MAX_AGE': 300,
        'CONN_HEALTH_CHECKS': True,
    }
    logger.info(f"[SUCCESS] Configured SCHEMA mode: {tenant_info.schema_name}")
    
    # Register connection
    connections.databases[connection_name] = db_config
    
    # Test connection
    try:
        with connections[connection_name].cursor() as cursor:
            cursor.execute("SELECT 1")
        logger.info(f"[SUCCESS] Connection test successful: {connection_name}")
    except Exception as e:
        logger.error(f"[ERROR] Connection test failed: {e}")
        if connection_name in connections.databases:
            del connections.databases[connection_name]
        raise
    
    return connection_name


def run_tenant_migrations(tenant_slug, connection_name):
    """
    Run company_compliance migrations on tenant schema
    SCHEMA mode: Sets search_path before running migrations
    """
    try:
        logger.info(f"[LOADING] Running migrations for {tenant_slug} on {connection_name}")
        
        # Get tenant info
        tenant = TenantDatabaseInfo.objects.get(tenant_slug=tenant_slug)
        
        # Set search_path to tenant schema
        with connections[connection_name].cursor() as cursor:
            cursor.execute(f"SET search_path TO {tenant.schema_name}, public;")
            logger.info(f"[SUCCESS] Set search_path to {tenant.schema_name}")
        
        # Run migrations using Django's call_command
        call_command(
            'migrate',
            'company_compliance',
            database=connection_name,
            verbosity=2,
            interactive=False,
            
        )
        
        logger.info(f"[SUCCESS] Migrations completed for {tenant_slug}")
        return {'success': True, 'message': 'Migrations completed'}
        
    except Exception as e:
        error_msg = f"Migration failed for {tenant_slug}: {str(e)}"
        logger.error(f"[ERROR] {error_msg}", exc_info=True)
        return {'success': False, 'error': error_msg}
    

def force_create_company_tables(connection_name, schema_name):
    """
    Force create all company_compliance tables
    Use when migrations fail (especially for SCHEMA isolation mode)
    """
    from company_compliance.models import (
        CompanyFramework, CompanyDomain, CompanyCategory, CompanySubcategory,
        CompanyControl, CompanyAssessmentQuestion, CompanyEvidenceRequirement,
        ControlAssignment, AssessmentCampaign, AssessmentResponse,
        EvidenceDocument, ComplianceReport
    )
    from django.db import transaction
    
    try:
        logger.info(f"[LOADING] Force creating tables for connection: {connection_name}")
        
        # Rollback any pending transaction first
        connection = connections[connection_name]
        if connection.in_atomic_block:
            logger.warning(f"[WARN] Rolling back failed transaction")
            connection.rollback()
        
        # Set search_path to tenant schema
        with connection.cursor() as cursor:
            cursor.execute(f"SET search_path TO {schema_name}, public;")
            logger.info(f"[SUCCESS] Set search_path to {schema_name}")
        
        # Create tables using atomic transaction
        with transaction.atomic(using=connection_name):
            with connection.schema_editor() as schema_editor:
                models = [
                    CompanyFramework, CompanyDomain, CompanyCategory, CompanySubcategory,
                    CompanyControl, CompanyAssessmentQuestion, CompanyEvidenceRequirement,
                    ControlAssignment, AssessmentCampaign, AssessmentResponse,
                    EvidenceDocument, ComplianceReport
                ]
                
                for model in models:
                    try:
                        schema_editor.create_model(model)
                        logger.info(f"[SUCCESS] Created table: {model._meta.db_table}")
                    except Exception as e:
                        # Table might already exist, check if that's the issue
                        if 'already exists' in str(e).lower():
                            logger.warning(f"[SKIP] Table {model._meta.db_table} already exists")
                        else:
                            # Real error, propagate it
                            raise
        
        logger.info(f"[SUCCESS] Force table creation completed")
        return {'success': True, 'message': 'Tables created manually'}
    
    except Exception as e:
        logger.error(f"[ERROR] Force table creation failed: {e}", exc_info=True)
        
        # Rollback connection on error
        try:
            connections[connection_name].rollback()
        except:
            pass
            
        return {'success': False, 'error': str(e)}


def create_tenant_record(tenant_slug, company_name, company_email, subscription_plan_code='BASIC'):
    """
    Create tenant record ONLY - no schema creation
    Used for payment-first flow
    
    Returns:
        dict: {
            'success': bool,
            'tenant_info': TenantDatabaseInfo,
            'payment_required': bool,
            'amount': Decimal
        }
    """
    logger.info(f"\n[TENANT RECORD] Creating tenant record: {company_name} ({tenant_slug})")
    
    try:
        # 1) Get subscription plan
        from .models import SubscriptionPlan
        subscription_plan = SubscriptionPlan.objects.get(code=subscription_plan_code)
        
        # 2) Check if tenant already exists
        from .models import TenantDatabaseInfo
        if TenantDatabaseInfo.objects.filter(tenant_slug=tenant_slug).exists():
            raise ValueError(f"Tenant with slug '{tenant_slug}' already exists")
        
        # 3) Create tenant record (minimal)
        schema_name = f"{tenant_slug}_schema"
        
        tenant_info = TenantDatabaseInfo.objects.create(
            tenant_slug=tenant_slug,
            company_name=company_name,
            company_email=company_email,
            database_name='main_compliance_system_db',
            database_user=settings.DATABASES['default']['USER'],
            database_host=settings.DATABASES['default']['HOST'],
            database_port=settings.DATABASES['default']['PORT'],
            subscription_plan=subscription_plan,
            subscription_status='PENDING_PAYMENT',  # ← Wait for payment
            provisioning_status='PENDING',          # ← Not provisioned yet
            schema_name=schema_name,
            is_active=False,  # ← Not active until payment
        )
        
        # Don't encrypt password since we're not creating schema yet
        tenant_info.database_password = ''
        tenant_info.save()
        
        logger.info(f"[SUCCESS] Tenant record created: {tenant_info.id}")
        logger.info(f"[INFO] Status: PENDING_PAYMENT - Awaiting payment confirmation")
        
        return {
            'success': True,
            'tenant_info': tenant_info,
            'payment_required': True,
            'amount': subscription_plan.monthly_price,
            'message': 'Tenant record created. Payment required to activate.'
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to create tenant record: {e}")
        raise


def activate_tenant_with_framework(tenant_slug, framework_id, customization_level='CONTROL_LEVEL'):
    """
    Activate tenant after payment success
    Creates schema, runs migrations, subscribes to framework
    
    This should be called AFTER payment is confirmed
    
    Returns:
        dict: {
            'success': bool,
            'tenant_info': TenantDatabaseInfo,
            'connection_name': str,
            'framework_name': str
        }
    """
    logger.info(f"\n[ACTIVATION] Activating tenant: {tenant_slug}")
    
    steps = {
        'get_tenant': None,
        'create_schema': None,
        'django_connection': None,
        'migrations': None,
        'framework_subscription': None,
        'final_status': None,
    }
    
    try:
        # 1) Get tenant record
        from .models import TenantDatabaseInfo
        tenant_info = TenantDatabaseInfo.objects.get(
            tenant_slug=tenant_slug,
            subscription_status='PENDING_PAYMENT'
        )
        steps['get_tenant'] = {'id': str(tenant_info.id)}
        logger.info(f"[INFO] Found tenant: {tenant_info.company_name}")
        
        # 2) Create PostgreSQL schema
        schema_name = tenant_info.schema_name
        create_postgresql_schema(schema_name)
        steps['create_schema'] = {'schema_name': schema_name}
        logger.info(f"[SUCCESS] Created schema: {schema_name}")
        
        # 3) Register Django connection
        connection_name = add_tenant_database_to_django(tenant_info)
        steps['django_connection'] = {'connection_name': connection_name}
        logger.info(f"[SUCCESS] Registered Django connection")
        
        # 4) Run migrations
        # 4) Create tables directly (more reliable than migrations for SCHEMA mode)
        logger.info(f"[LOADING] Creating tables directly in {tenant_info.schema_name}")
        
        migration_result = force_create_company_tables(
            connection_name=connection_name,
            schema_name=tenant_info.schema_name
        )
        steps['migrations'] = migration_result
        
        if not migration_result['success']:
            raise Exception(f"Failed to create tables: {migration_result.get('error')}")
        
        logger.info(f"[SUCCESS] Tables created in {tenant_info.schema_name}")
            

        # 4.5) Set tenant to ACTIVE before framework distribution
        tenant_info.subscription_status = 'ACTIVE'
        tenant_info.provisioning_status = 'ACTIVE'
        tenant_info.is_active = True
        tenant_info.save()
        logger.info(f"[SUCCESS] Tenant status set to ACTIVE")
        
        
        # 5) Subscribe to framework
        from templates_host.distribution_utils import copy_framework_to_tenant
        
        distribution_result = copy_framework_to_tenant(
            tenant=tenant_info,
            framework_id=framework_id,
            customization_level=customization_level
        )
        
        if not distribution_result['success']:
            raise Exception(f"Framework distribution failed: {distribution_result.get('error')}")
        
        steps['framework_subscription'] = {
            'framework_id': framework_id,
            'framework_name': distribution_result.get('framework_name'),
            'customization_level': customization_level
        }
        logger.info(f"[SUCCESS] Framework subscribed: {distribution_result.get('framework_name')}")
        
       
        tenant_info.subscription_start_date = timezone.now().date()
        tenant_info.provisioned_at = timezone.now()
        tenant_info.save()
        
        steps['final_status'] = 'ACTIVE'
        logger.info(f"[SUCCESS] Tenant {tenant_slug} activated successfully!")
        
        # 7) Invalidate cache
        invalidate_tenant_cache(tenant_slug)
        
        return {
            'success': True,
            'tenant_info': tenant_info,
            'connection_name': connection_name,
            'framework_name': distribution_result.get('framework_name'),
            'steps': steps,
            'message': 'Tenant activated and framework subscribed successfully'
        }
        
    except TenantDatabaseInfo.DoesNotExist:
        logger.error(f"[ERROR] Tenant not found or already activated: {tenant_slug}")
        raise ValueError(f"Tenant '{tenant_slug}' not found or already activated")
        
    except Exception as e:
        logger.error(f"[ERROR] Activation failed: {e}")
        
        # Rollback: Update tenant status to failed
        if 'tenant_info' in locals():
            tenant_info.provisioning_status = 'FAILED'
            tenant_info.provisioning_error = str(e)
            tenant_info.save()
        
        raise


def delete_pending_tenant(tenant_slug):
    """
    Delete tenant record if payment failed
    Only works if status is PENDING_PAYMENT and no schema exists
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    logger.info(f"\n[CLEANUP] Deleting pending tenant: {tenant_slug}")
    
    try:
        from .models import TenantDatabaseInfo
        
        tenant_info = TenantDatabaseInfo.objects.get(
            tenant_slug=tenant_slug,
            subscription_status='PENDING_PAYMENT',
            provisioning_status='PENDING'
        )
        
        # Mark as deleted instead of hard delete (for audit trail)
        tenant_info.subscription_status = 'DELETED'
        tenant_info.is_active = False
        tenant_info.save()
        
        logger.info(f"[SUCCESS] Tenant marked as deleted: {tenant_slug}")
        
        return {
            'success': True,
            'message': f'Tenant {tenant_slug} deleted (payment not completed)'
        }
        
    except TenantDatabaseInfo.DoesNotExist:
        logger.warning(f"[WARN] Tenant not found or already provisioned: {tenant_slug}")
        return {
            'success': False,
            'message': 'Tenant not found or already activated'
        }
    except Exception as e:
        logger.error(f"[ERROR] Failed to delete tenant: {e}")
        raise

def load_all_tenant_databases():
    """Load all active tenant databases into Django connections at startup"""
    logger.info("[LOADING] Loading tenant databases...")
    
    for tenant_info in TenantDatabaseInfo.objects.filter(
        is_active=True,
        provisioning_status='ACTIVE'
    ):
        try:
            add_tenant_database_to_django(tenant_info)
            logger.info(f"[SUCCESS] Loaded: {tenant_info.tenant_slug}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load {tenant_info.tenant_slug}: {e}")
    
    logger.info("[SUCCESS] All tenant databases loaded")


def get_cached_tenant_db_info(tenant_slug):
    """Get tenant database info from cache or database"""
    cache_key = f"tenant_db_info:{tenant_slug}"
    data = cache.get(cache_key)
    
    if not data:
        try:
            tenant = TenantDatabaseInfo.objects.get(
                tenant_slug=tenant_slug,
                is_active=True
            )
            
            data = {
                'tenant_slug': tenant.tenant_slug,
                'company_name': tenant.company_name,
                'status': tenant.subscription_status,
                'provisioning_status': tenant.provisioning_status,
                'schema_name': tenant.schema_name,
            }
            
            cache.set(cache_key, data, CACHE_TTL_SECONDS)
            logger.info(f"Cached tenant info: {tenant_slug}")
            
        except TenantDatabaseInfo.DoesNotExist:
            return None
    
    return data


def invalidate_tenant_cache(tenant_slug):
    """Invalidate cached tenant data"""
    cache_key = f"tenant_db_info:{tenant_slug}"
    cache.delete(cache_key)
    logger.info(f"Invalidated cache: {tenant_slug}")

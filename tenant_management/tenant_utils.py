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


def generate_database_credentials(tenant_slug):
    """Generate secure database credentials for tenant"""
    db_name = f"{tenant_slug}_compliance_db"
    db_user = f"{tenant_slug}_user"
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    return db_name, db_user, password


def create_postgresql_database(db_name, db_user, db_password):
    """
    Create PostgreSQL database and user (DATABASE isolation mode)
    Idempotent: Won't fail if already exists
    """
    conn = psycopg2.connect(
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        database='postgres'
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        # 1) Create user if doesn't exist
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s;", (db_user,))
        role_exists = cursor.fetchone() is not None

        if not role_exists:
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s")
                .format(sql.Identifier(db_user)),
                (db_password,)
            )
            logger.info(f"[SUCCESS] Created database user: {db_user}")
        else:
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s")
                .format(sql.Identifier(db_user)),
                (db_password,)
            )
            logger.info(f"[UPDATE] Updated password for user: {db_user}")

        # 2) Create database if doesn't exist
        cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s;", (db_name,))
        db_exists = cursor.fetchone() is not None

        if not db_exists:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}")
                .format(sql.Identifier(db_name), sql.Identifier(db_user))
            )
            logger.info(f"[SUCCESS] Created database: {db_name}")
        else:
            logger.info(f"[UPDATE] Database already exists: {db_name}")

        # 3) Grant privileges
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}")
            .format(sql.Identifier(db_name), sql.Identifier(db_user))
        )
        logger.info(f"[SUCCESS] Granted privileges to {db_user} on {db_name}")

    except Exception as e:
        logger.error(f"[ERROR] Error creating database: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


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
    Register tenant database/schema in Django connections
    Supports both DATABASE and SCHEMA isolation modes
    """
    connection_name = f"{tenant_info.tenant_slug}_compliance_db"
    
    # Check if already registered
    if connection_name in connections.databases:
        logger.info(f"[UPDATE] Connection {connection_name} already registered")
        return connection_name
    
    default_db = settings.DATABASES['default'].copy()
    
    if tenant_info.isolation_mode == 'SCHEMA':
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
    else:
        # DATABASE mode: Separate database
        db_config = {
            **default_db,
            'NAME': tenant_info.database_name,
            'USER': tenant_info.database_user,
            'PASSWORD': tenant_info.decrypt_password(),
            'HOST': tenant_info.database_host,
            'PORT': tenant_info.database_port,
            'CONN_MAX_AGE': 300,
            'CONN_HEALTH_CHECKS': True,
        }
        logger.info(f"[SUCCESS] Configured DATABASE mode: {tenant_info.database_name}")
    
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
    Run company_compliance migrations on tenant database/schema
    MONOLITH VERSION - No service calls!
    """
    try:
        logger.info(f"[LOADING] Running migrations for {tenant_slug} on {connection_name}")
        
        # Get tenant info to determine isolation mode
        tenant = TenantDatabaseInfo.objects.get(tenant_slug=tenant_slug)
        
        # For SCHEMA mode, set search_path before migrations
        if tenant.isolation_mode == 'SCHEMA':
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
            run_syncdb=True
        )
        
        logger.info(f"[SUCCESS] Migrations completed for {tenant_slug}")
        return {'success': True, 'message': 'Migrations completed'}
        
    except Exception as e:
        error_msg = f"Migration failed for {tenant_slug}: {str(e)}"
        logger.error(f"[ERROR] {error_msg}", exc_info=True)
        return {'success': False, 'error': error_msg}
    

def force_create_company_tables(connection_name, schema_name=None):
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
    
    try:
        logger.info(f"[LOADING] Force creating tables for connection: {connection_name}")
        
        with connections[connection_name].cursor() as cursor:
            # Set search_path if schema mode
            if schema_name:
                cursor.execute(f"SET search_path TO {schema_name}, public;")
                logger.info(f"[SUCCESS] Set search_path to {schema_name}")
        
        # Create tables using schema editor
        with connections[connection_name].schema_editor() as schema_editor:
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
                    # Table might already exist, that's okay
                    logger.debug(f"[INFO] Table {model._meta.db_table}: {str(e)}")
        
        logger.info(f"[SUCCESS] Force table creation completed")
        return {'success': True, 'message': 'Tables created manually'}
    
    except Exception as e:
        logger.error(f"[ERROR] Force table creation failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def provision_tenant(tenant_slug, company_name, subscription_plan_code='BASIC'):
    """
    Complete tenant provisioning - MONOLITH VERSION
    Creates database/schema, runs migrations, ready for frameworks
    """
    logger.info(f"\n[PROVISIONING] Provisioning tenant: {company_name} ({tenant_slug})")
    
    steps = {
        'credentials': None,
        'tenant_record': None,
        'isolation_decision': None,
        'postgres_provision': None,
        'django_connection': None,
        'migrations': None,
        'final_status': None,
    }
    
    try:
        # 1) Get subscription plan
        from .models import SubscriptionPlan
        subscription_plan = SubscriptionPlan.objects.get(code=subscription_plan_code)
        
        # 2) Decide isolation mode
        # if subscription_plan.code == 'ENTERPRISE':
        #     isolation_mode = 'DATABASE'
        # else:
        #     isolation_mode = 'SCHEMA'
        isolation_mode = 'SCHEMA'
        
        steps['isolation_decision'] = {'mode': isolation_mode, 'plan': subscription_plan_code}
        logger.info(f"[INFO] Isolation mode: {isolation_mode}")
        
        # 3) Generate credentials
        # if isolation_mode == 'DATABASE':
        #     db_name, db_user, db_password = generate_database_credentials(tenant_slug)
        #     schema_name = None
        # else:
        #     db_name = 'main_compliance_system_db'
        #     db_user = settings.DATABASES['default']['USER']
        #     db_password = settings.DATABASES['default']['PASSWORD']
        #     schema_name = f"{tenant_slug}_schema"

        db_name = 'main_compliance_system_db'
        db_user = settings.DATABASES['default']['USER']
        db_password = settings.DATABASES['default']['PASSWORD']
        schema_name = f"{tenant_slug}_schema"

        
        steps['credentials'] = {
            'db_name': db_name,
            'schema_name': schema_name,
            'mode': isolation_mode
        }
        
        # 4) Create tenant record
        tenant_info = TenantDatabaseInfo.objects.create(
            tenant_slug=tenant_slug,
            company_name=company_name,
            database_name=db_name,
            database_user=db_user,
            database_host=settings.DATABASES['default']['HOST'],
            database_port=settings.DATABASES['default']['PORT'],
            subscription_plan=subscription_plan,
            provisioning_status='PROVISIONING',
            isolation_mode=isolation_mode,
            schema_name=schema_name,
            is_active=True,\
            subscription_start_date=timezone.now().date(),  # ✅ ADD THIS
            trial_end_date=timezone.now().date() + timedelta(days=30),  # ✅ ADD THIS (30-day trial)
        )
        tenant_info.encrypt_password(db_password)
        tenant_info.save()
        steps['tenant_record'] = {'id': str(tenant_info.id)}
        logger.info(f"[SUCCESS] Created tenant record: {tenant_info.id}")
        
        # 5) Create PostgreSQL database or schema
        # if isolation_mode == 'DATABASE':
        #     create_postgresql_database(db_name, db_user, db_password)
        #     steps['postgres_provision'] = {'type': 'database', 'name': db_name}
        # else:
        #     create_postgresql_schema(schema_name)
        #     steps['postgres_provision'] = {'type': 'schema', 'name': schema_name}
        
        create_postgresql_schema(schema_name)
        steps['postgres_provision'] = {'type': 'schema', 'name': schema_name}


        # 6) Register Django connection
        connection_name = add_tenant_database_to_django(tenant_info)
        steps['django_connection'] = {'connection_name': connection_name}
        
        # 7) Run migrations
        # 7) Run migrations
        migration_result = run_tenant_migrations(tenant_slug, connection_name)
        steps['migrations'] = migration_result
        
        # 7b) If migrations failed, force create tables
        if not migration_result['success']:
            logger.warning(f"[WARN] Migrations failed, forcing table creation...")
            force_result = force_create_company_tables(
                connection_name=connection_name,
                schema_name=tenant_info.schema_name if tenant_info.isolation_mode == 'SCHEMA' else None
            )
            steps['force_tables'] = force_result
            
            # Update migration result if force creation succeeded
            if force_result['success']:
                migration_result = force_result
                logger.info(f"[SUCCESS] Tables created via force method")
        
        # 8) Update status
        if migration_result['success']:
            tenant_info.provisioning_status = 'ACTIVE'
            tenant_info.subscription_status = 'TRIAL'  # Start with trial
            logger.info(f"[SUCCESS] Tenant {tenant_slug} provisioned successfully!")
        else:
            tenant_info.provisioning_status = 'FAILED'
            logger.error(f"[ERROR] Tenant {tenant_slug} provisioning failed")
        
        tenant_info.save()
        steps['final_status'] = tenant_info.provisioning_status
        
        return {
            'success': migration_result['success'],
            'tenant_info': tenant_info,
            'connection_name': connection_name,
            'steps': steps
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Provisioning error: {e}")
        if 'tenant_info' in locals():
            tenant_info.provisioning_status = 'FAILED'
            tenant_info.save()
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
                'isolation_mode': tenant.isolation_mode,
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

"""
Seed initial data for Vibe Connect Compliance Platform
Creates subscription plans, roles, permissions, and framework categories

Usage:
    python manage.py seed_initial_data
    python manage.py seed_initial_data --reset  # Delete existing data first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from tenant_management.models import SubscriptionPlan
from user_management.models import Role, RolePermission
from templates_host.models import FrameworkCategory
from django.utils import timezone


class Command(BaseCommand):
    help = 'Seeds initial data: subscription plans, roles, permissions, framework categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing data before seeding (dangerous!)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🌱 SEEDING INITIAL DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if options['reset']:
            self.stdout.write(self.style.WARNING('\n⚠️  RESET MODE: Deleting existing data...'))
            self.reset_data()

        with transaction.atomic():
            self.seed_subscription_plans()
            self.seed_roles_and_permissions()
            self.seed_framework_categories()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ SEEDING COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

    def reset_data(self):
        """Delete existing data (use with caution!)"""
        RolePermission.objects.all().delete()
        Role.objects.filter(is_system_role=False).delete()  # Keep system roles
        SubscriptionPlan.objects.all().delete()
        FrameworkCategory.objects.all().delete()
        self.stdout.write(self.style.WARNING('  ✓ Existing data deleted\n'))

    def seed_subscription_plans(self):
        """Create subscription plans"""
        self.stdout.write(self.style.HTTP_INFO('\n📋 Creating Subscription Plans...'))

        plans_data = [
            {
                'code': 'BASIC',
                'name': 'Basic Plan',
                'description': 'Perfect for small teams getting started with compliance. '
                               'View-only access to framework templates with basic reporting.',
                'monthly_price': 299.00,
                'annual_price': 2990.00,  # ~17% discount
                'max_users': 10,
                'max_frameworks': 2,
                'max_controls': 500,
                'storage_gb': 10,
                'can_create_custom_frameworks': False,
                'can_customize_controls': False,
                'has_api_access': False,
                'has_advanced_reporting': False,
                'has_sso': False,
                'default_isolation_mode': 'SCHEMA',
                'default_customization_level': 'VIEW_ONLY',
                'support_level': 'EMAIL',
                'sort_order': 1,
            },
            {
                'code': 'PROFESSIONAL',
                'name': 'Professional Plan',
                'description': 'For growing teams that need control customization. '
                               'Customize controls to fit your organization with advanced reporting.',
                'monthly_price': 599.00,
                'annual_price': 5990.00,  # ~17% discount
                'max_users': 50,
                'max_frameworks': 5,
                'max_controls': 2000,
                'storage_gb': 50,
                'can_create_custom_frameworks': False,
                'can_customize_controls': True,
                'has_api_access': True,
                'has_advanced_reporting': True,
                'has_sso': False,
                'default_isolation_mode': 'SCHEMA',
                'default_customization_level': 'CONTROL_LEVEL',
                'support_level': 'PRIORITY',
                'sort_order': 2,
            },
            {
                'code': 'ENTERPRISE',
                'name': 'Enterprise Plan',
                'description': 'Complete compliance solution with dedicated infrastructure. '
                               'Full customization, SSO, API access, and dedicated support.',
                'monthly_price': 1499.00,
                'annual_price': 14990.00,  # ~17% discount
                'max_users': 0,  # Unlimited
                'max_frameworks': 0,  # Unlimited
                'max_controls': 0,  # Unlimited
                'storage_gb': 500,
                'can_create_custom_frameworks': True,
                'can_customize_controls': True,
                'has_api_access': True,
                'has_advanced_reporting': True,
                'has_sso': True,
                'default_isolation_mode': 'DATABASE',  # Dedicated database
                'default_customization_level': 'FULL',
                'support_level': 'DEDICATED',
                'sort_order': 3,
            },
        ]

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                code=plan_data['code'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {plan.name} (${plan.monthly_price}/mo)'))
            else:
                self.stdout.write(self.style.WARNING(f'  ↻ Updated: {plan.name} (${plan.monthly_price}/mo)'))

    def seed_roles_and_permissions(self):
        """Create roles and their permissions"""
        self.stdout.write(self.style.HTTP_INFO('\n👥 Creating Roles & Permissions...'))

        roles_data = [
            {
                'code': 'TENANT_ADMIN',
                'name': 'Tenant Administrator',
                'description': 'Full administrative control over the tenant. Can manage users, '
                               'frameworks, and all compliance activities.',
                'is_system_role': True,
                'permissions': [
                    # Administrative
                    ('manage_users', 'Can manage users', 'Invite, remove, and manage user roles'),
                    ('manage_frameworks', 'Can manage frameworks', 'Subscribe to and customize frameworks'),
                    ('manage_settings', 'Can manage settings', 'Update company settings and preferences'),
                    ('manage_billing', 'Can manage billing', 'View and manage billing information'),
                    ('view_audit_logs', 'Can view audit logs', 'View system audit logs'),
                    
                    # Control & Campaign Management
                    ('assign_controls', 'Can assign controls', 'Assign controls to team members'),
                    ('create_campaigns', 'Can create campaigns', 'Create and manage assessment campaigns'),
                    
                    # Reporting
                    ('view_reports', 'Can view reports', 'View compliance reports and analytics'),
                    ('generate_reports', 'Can generate reports', 'Generate compliance reports'),
                    ('export_data', 'Can export data', 'Export compliance data'),
                    
                    # ⭐ NEW: Approval Workflow Permissions
                    ('approve_assignments', 'Can approve assignments', 'Approve control assignments'),
                    ('reject_assignments', 'Can reject assignments', 'Reject control assignments'),
                    ('approve_responses', 'Can approve responses', 'Approve assessment responses'),
                    ('reject_responses', 'Can reject responses', 'Reject assessment responses'),
                    ('verify_evidence', 'Can verify evidence', 'Verify evidence documents'),
                    ('reject_evidence', 'Can reject evidence', 'Reject evidence documents'),
                ]
            },
            {
                'code': 'COMPLIANCE_MANAGER',
                'name': 'Compliance Manager',
                'description': 'Manages compliance activities and assessments. Can create campaigns, '
                               'assign controls, review responses, and verify evidence.',
                'is_system_role': True,
                'permissions': [
                    # Control & Campaign Management
                    ('assign_controls', 'Can assign controls', 'Assign controls to team members'),
                    ('create_campaigns', 'Can create campaigns', 'Create and manage assessment campaigns'),
                    
                    # Review & Approval
                    ('review_responses', 'Can review responses', 'Review and approve assessment responses'),
                    ('manage_evidence', 'Can manage evidence', 'Upload and manage evidence documents'),
                    ('customize_controls', 'Can customize controls', 'Customize control descriptions'),
                    
                    # Reporting
                    ('view_reports', 'Can view reports', 'View compliance reports and analytics'),
                    ('generate_reports', 'Can generate reports', 'Generate compliance reports'),
                    
                    # ⭐ NEW: Approval Workflow Permissions
                    ('approve_assignments', 'Can approve assignments', 'Approve control assignments'),
                    ('reject_assignments', 'Can reject assignments', 'Reject control assignments'),
                    ('approve_responses', 'Can approve responses', 'Approve assessment responses'),
                    ('reject_responses', 'Can reject responses', 'Reject assessment responses'),
                    ('verify_evidence', 'Can verify evidence', 'Verify evidence documents'),
                    ('reject_evidence', 'Can reject evidence', 'Reject evidence documents'),
                ]
            },
            {
                'code': 'MANAGER',
                'name': 'Manager',
                'description': 'Team manager with approval authority. Can assign controls and '
                               'approve team assignments.',
                'is_system_role': True,
                'permissions': [
                    # Control Management
                    ('assign_controls', 'Can assign controls', 'Assign controls to team members'),
                    ('view_frameworks', 'Can view frameworks', 'View all frameworks and controls'),
                    ('view_responses', 'Can view responses', 'View all assessment responses'),
                    ('view_evidence', 'Can view evidence', 'View all evidence documents'),
                    ('view_reports', 'Can view reports', 'View compliance reports'),
                    
                    # ⭐ NEW: Assignment Approval (Manager-level only)
                    ('approve_assignments', 'Can approve assignments', 'Approve control assignments'),
                    ('reject_assignments', 'Can reject assignments', 'Reject control assignments'),
                ]
            },
            {
                'code': 'EMPLOYEE',
                'name': 'Employee',
                'description': 'Standard user with access to assigned controls. Can complete assessments '
                               'and upload evidence for assigned controls.',
                'is_system_role': True,
                'permissions': [
                    ('view_assigned_controls', 'Can view assigned controls', 'View controls assigned to them'),
                    ('submit_responses', 'Can submit responses', 'Submit assessment responses'),
                    ('upload_evidence', 'Can upload evidence', 'Upload evidence for assigned controls'),
                    ('view_own_assignments', 'Can view own assignments', 'View their own assignments'),
                ]
            },
            {
                'code': 'AUDITOR',
                'name': 'Auditor',
                'description': 'Read-only access for external or internal auditors. Can view frameworks, '
                               'controls, responses, and evidence but cannot make changes.',
                'is_system_role': True,
                'permissions': [
                    ('view_frameworks', 'Can view frameworks', 'View all frameworks and controls'),
                    ('view_responses', 'Can view responses', 'View all assessment responses'),
                    ('view_evidence', 'Can view evidence', 'View all evidence documents'),
                    ('view_reports', 'Can view reports', 'View compliance reports'),
                    ('export_data', 'Can export data', 'Export compliance data'),
                ]
            },
        ]

        for role_data in roles_data:
            permissions = role_data.pop('permissions')
            
            role, created = Role.objects.update_or_create(
                code=role_data['code'],
                defaults=role_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created role: {role.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'  ↻ Updated role: {role.name}'))

            # Create permissions
            for perm_code, perm_name, perm_desc in permissions:
                perm, perm_created = RolePermission.objects.update_or_create(
                    role=role,
                    permission_code=perm_code,
                    defaults={
                        'permission_name': perm_name,
                        'description': perm_desc
                    }
                )
                if perm_created:
                    self.stdout.write(f'    → Added permission: {perm_code}')
                    
    def seed_framework_categories(self):
        """Create framework categories"""
        self.stdout.write(self.style.HTTP_INFO('\n📁 Creating Framework Categories...'))

        categories_data = [
            {
                'name': 'Financial Compliance',
                'code': 'FIN',
                'description': 'Financial regulations, auditing standards, and fiscal controls. '
                               'Includes frameworks like SOX, FINRA, and Basel III.',
                'icon': 'bank',
                'color': '#10B981',
                'sort_order': 1,
            },
            {
                'name': 'Security & Privacy',
                'code': 'SEC',
                'description': 'Information security, data privacy, and cybersecurity frameworks. '
                               'Includes ISO 27001, NIST CSF, and SOC 2.',
                'icon': 'shield',
                'color': '#3B82F6',
                'sort_order': 2,
            },
            {
                'name': 'Data Protection',
                'code': 'PRIV',
                'description': 'Data privacy regulations and personal data protection. '
                               'Includes GDPR, CCPA, and PIPEDA.',
                'icon': 'lock',
                'color': '#8B5CF6',
                'sort_order': 3,
            },
            {
                'name': 'Healthcare',
                'code': 'HEALTH',
                'description': 'Healthcare compliance and patient data protection. '
                               'Includes HIPAA, HITRUST, and FDA 21 CFR Part 11.',
                'icon': 'health',
                'color': '#EF4444',
                'sort_order': 4,
            },
            {
                'name': 'Industry Standards',
                'code': 'IND',
                'description': 'Industry-specific standards and best practices. '
                               'Includes PCI DSS, COBIT, and ITIL.',
                'icon': 'industry',
                'color': '#F59E0B',
                'sort_order': 5,
            },
        ]

        for category_data in categories_data:
            category, created = FrameworkCategory.objects.update_or_create(
                code=category_data['code'],
                defaults=category_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {category.name} ({category.code})'))
            else:
                self.stdout.write(self.style.WARNING(f'  ↻ Updated: {category.name} ({category.code})'))
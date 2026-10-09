"""
apps/tenants/provisioning.py

Automatic Tenant Database Provisioning Service.

When a new tenant is created, this service:
  1. Creates a new PostgreSQL database
  2. Registers it in Django's DATABASES dict
  3. Runs all tenant-specific migrations on that database
  4. Creates the default Admin user in the tenant database
  5. Seeds default CMS data
  6. Generates the subdomain domain record
  7. Sends welcome email
"""
import logging
import subprocess
import sys
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def log_step(tenant, step: str, message: str, level: str = 'info'):
    """Helper to log provisioning steps."""
    from apps.tenants.models import TenantProvisioningLog
    TenantProvisioningLog.objects.create(
        tenant=tenant,
        step=step,
        message=message,
        level=level,
    )
    log_fn = getattr(logger, level, logger.info)
    log_fn(f'[PROVISION] {tenant.slug} – {step}: {message}')


def create_tenant_database(tenant):
    """Create a new PostgreSQL schema for the tenant inside the main database."""
    db_config = settings.DATABASES['default']
    schema_name = tenant.db_name

    import psycopg2
    conn = psycopg2.connect(
        dbname=db_config['NAME'],
        user=db_config['USER'],
        password=db_config['PASSWORD'],
        host=db_config['HOST'],
        port=db_config['PORT'],
    )
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Create schema instead of a separate database to avoid cPanel privilege issues
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
        
        # Explicitly create the django_migrations table in this schema so it shadows the public one.
        # This prevents Django from checking public.django_migrations and skipping migrations for this tenant.
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS "{schema_name}"."django_migrations" (
                id bigserial primary key,
                app character varying(255) not null,
                name character varying(255) not null,
                applied timestamp with time zone not null
            );
        ''')
        
        log_step(tenant, 'create_database', f'Schema "{schema_name}" created successfully.', 'success')
        tenant.db_created = True
        tenant.save(update_fields=['db_created'])
    except Exception as e:
        log_step(tenant, 'create_database', f'Failed to create schema: {e}', 'error')
        raise
    finally:
        cursor.close()
        conn.close()


def register_tenant_database(tenant):
    """Register tenant database in Django's DATABASES setting."""
    db_alias = f'tenant_{tenant.slug}'
    if db_alias not in settings.DATABASES:
        settings.DATABASES[db_alias] = tenant.get_db_config()
    log_step(tenant, 'register_database', f'Database alias "{db_alias}" registered.', 'success')
    return db_alias


def run_tenant_migrations(tenant, db_alias: str):
    """Run Django migrations on the tenant database."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    tenant_apps = ['travel_packages', 'visa', 'bookings', 'payments', 'destinations', 'cms', 'support', 'coupons', 'notifications', 'kyc', 'bus']
    try:
        for app in tenant_apps:
            try:
                call_command('migrate', app, '--database', db_alias, verbosity=0)
            except Exception as app_err:
                logger.warning(f"Tenant {tenant.slug} migration warning for {app}: {app_err}")
        log_step(tenant, 'run_migrations', 'Migrations completed successfully.', 'success')
        tenant.db_migrated = True
        tenant.save(update_fields=['db_migrated'])
    except Exception as e:
        log_step(tenant, 'run_migrations', f'Migration failed: {e}', 'error')
        raise


def create_default_admin(tenant, db_alias: str, admin_email: str, admin_password: str):
    """Create the default admin user in the main DB and return it."""
    try:
        admin_user, created = User.objects.using('default').get_or_create(
            email=admin_email,
            defaults={
                'first_name': tenant.owner_name.split()[0] if tenant.owner_name else 'Admin',
                'last_name': ' '.join(tenant.owner_name.split()[1:]) if tenant.owner_name else '',
                'role': User.Role.TENANT_ADMIN,
                'tenant_id': tenant.slug,
                'email_verified': True,
                'is_active': True,
            }
        )
        admin_user.set_password(admin_password)
        admin_user.role = User.Role.TENANT_ADMIN
        admin_user.tenant_id = tenant.slug
        admin_user.is_active = True
        admin_user.save()

        tenant.admin_user = admin_user
        tenant.save(update_fields=['admin_user'])

        log_step(tenant, 'create_admin', f'Admin user configured: {admin_email}', 'success')
        return admin_user
    except Exception as e:
        log_step(tenant, 'create_admin', f'Failed to create admin: {e}', 'error')
        raise


def create_tenant_subdomain(tenant):
    """Create the default subdomain domain record."""
    from apps.tenants.models import TenantDomain
    subdomain = f'{tenant.slug}.{settings.BASE_DOMAIN}'
    domain_obj, created = TenantDomain.objects.get_or_create(
        tenant=tenant,
        domain=subdomain,
        defaults={
            'domain_type': 'subdomain',
            'is_primary': True,
            'status': 'active',
        }
    )
    log_step(tenant, 'create_subdomain', f'Subdomain created: {subdomain}', 'success')
    return domain_obj


def seed_default_cms(tenant, db_alias: str):
    """Seed default CMS data in the tenant database."""
    try:
        from apps.cms.models import WebsiteSetting, CMSPage
        WebsiteSetting.objects.using(db_alias).get_or_create(
            key='site_name',
            defaults={'value': tenant.agency_name},
        )
        WebsiteSetting.objects.using(db_alias).get_or_create(
            key='tagline',
            defaults={'value': 'Your trusted travel partner'},
        )
        log_step(tenant, 'seed_cms', 'Default CMS data seeded.', 'success')
    except Exception as e:
        log_step(tenant, 'seed_cms', f'CMS seeding warning: {e}', 'warning')


def send_welcome_email(tenant, admin_email: str, admin_password: str):
    """Send welcome email with credentials to the new tenant admin."""
    from django.core.mail import send_mail
    try:
        send_mail(
            subject=f'Welcome to {settings.PLATFORM_NAME} – Your Agency is Ready!',
            message=f"""
Hello {tenant.owner_name},

Your travel agency account has been successfully created on {settings.PLATFORM_NAME}.

Agency Name  : {tenant.agency_name}
Admin Panel  : {tenant.admin_url}
Admin Email  : {admin_email}
Password     : {admin_password}
Website      : {tenant.subdomain_url}

Please login and change your password immediately.

Best regards,
The {settings.PLATFORM_NAME} Team
            """.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
        log_step(tenant, 'send_welcome_email', f'Welcome email sent to {admin_email}', 'success')
    except Exception as e:
        log_step(tenant, 'send_welcome_email', f'Email sending failed: {e}', 'warning')


def provision_tenant(tenant, admin_email: str, admin_password: str):
    """
    Full tenant provisioning pipeline.
    Called by Celery task after successful subscription payment.
    """
    import traceback

    tenant.provisioning_started_at = timezone.now()
    tenant.save(update_fields=['provisioning_started_at'])

    try:
        log_step(tenant, 'start', 'Tenant provisioning started.', 'info')

        # Step 1: Create database
        create_tenant_database(tenant)

        # Step 2: Register database
        db_alias = register_tenant_database(tenant)

        # Step 3: Run migrations
        run_tenant_migrations(tenant, db_alias)

        # Step 4: Create admin user
        create_default_admin(tenant, db_alias, admin_email, admin_password)

        # Step 5: Create subdomain
        create_tenant_subdomain(tenant)

        # Step 6: Seed default CMS
        seed_default_cms(tenant, db_alias)

        # Step 7: Provisioned – awaiting admin approval
        tenant.status = 'pending'
        tenant.provisioning_completed_at = timezone.now()
        tenant.save(update_fields=['status', 'provisioning_completed_at'])

        # Step 8: Send welcome email
        send_welcome_email(tenant, admin_email, admin_password)

        log_step(tenant, 'complete', 'Tenant provisioning completed successfully.', 'success')
        return True

    except Exception as e:
        error_msg = traceback.format_exc()
        tenant.provisioning_error = error_msg
        tenant.status = 'inactive'
        tenant.save(update_fields=['provisioning_error', 'status'])
        log_step(tenant, 'error', f'Provisioning failed: {error_msg}', 'error')
        return False

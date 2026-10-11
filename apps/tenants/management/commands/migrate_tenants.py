"""
apps/tenants/management/commands/migrate_tenants.py

Management command to safely create / migrate all agency database tables
in the public (default) schema AND in every existing tenant schema.

Usage:
    python manage.py migrate_tenants

This command is safe to re-run on an already-provisioned database; it is
idempotent – Django's migration framework won't re-apply already-applied
migrations.

Why this is needed:
    The previous router configuration blocked `allow_migrate` for
    TENANT_SPECIFIC_MODELS on the default database, so running
    `python manage.py migrate` never created tables like `tenants_visalot`.
    This command fixes both the public schema and all tenant schemas.
"""
import logging

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

TENANT_APPS = [
    'tenants',          # agency models: VisaLot, Candidate, AgencyAgent, etc.
    'travel_packages',
    'visa',
    'bookings',
    'payments',
    'destinations',
    'cms',
    'support',
    'coupons',
    'notifications',
    'kyc',
    'bus',
]


class Command(BaseCommand):
    help = (
        'Apply all agency / tenant migrations to the default (public) database '
        'and to every registered tenant schema database.'
    )

    def handle(self, *args, **options):
        # ── Step 1: Migrate the public / default database ─────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== Migrating PUBLIC schema (default database) ==='
        ))
        for app in TENANT_APPS:
            try:
                call_command('migrate', app, '--database', 'default', verbosity=1)
                self.stdout.write(self.style.SUCCESS(f'  [OK] {app} → default'))
            except Exception as err:
                self.stdout.write(self.style.WARNING(f'  [WARN] {app} → default: {err}'))

        # ── Step 2: Migrate every tenant schema ──────────────────────────────
        from apps.tenants.models import Tenant
        from apps.tenants.provisioning import create_tenant_database

        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING('\nNo tenant records found – skipping tenant schemas.'))
            return

        for tenant in tenants:
            db_alias = f'tenant_{tenant.slug}'
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n=== Migrating tenant: {tenant.agency_name} ({db_alias}) ==='
            ))

            # Register the db alias if not already present
            if db_alias not in settings.DATABASES:
                settings.DATABASES[db_alias] = tenant.get_db_config()

            # Ensure the schema and django_migrations table exist in this schema
            if not tenant.db_created:
                self.stdout.write(f'  Creating schema for {tenant.slug} ...')
                try:
                    create_tenant_database(tenant)
                    self.stdout.write(self.style.SUCCESS(f'  Schema created.'))
                except Exception as err:
                    self.stdout.write(self.style.ERROR(f'  [ERROR] Could not create schema: {err}'))
                    continue
            else:
                # Schema should already exist; make sure the django_migrations
                # table was created inside it (some older tenants may be missing it).
                try:
                    import psycopg2
                    db_cfg = settings.DATABASES['default']
                    conn = psycopg2.connect(
                        dbname=db_cfg['NAME'],
                        user=db_cfg['USER'],
                        password=db_cfg['PASSWORD'],
                        host=db_cfg['HOST'],
                        port=db_cfg['PORT'],
                    )
                    conn.autocommit = True
                    cur = conn.cursor()
                    schema = tenant.db_name
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}";')
                    cur.execute(f'''
                        CREATE TABLE IF NOT EXISTS "{schema}"."django_migrations" (
                            id bigserial primary key,
                            app character varying(255) not null,
                            name character varying(255) not null,
                            applied timestamp with time zone not null
                        );
                    ''')
                    cur.close()
                    conn.close()
                except Exception as err:
                    self.stdout.write(self.style.WARNING(f'  [WARN] Schema prep: {err}'))

            # Run migrations
            for app in TENANT_APPS:
                try:
                    call_command('migrate', app, '--database', db_alias, verbosity=1)
                    self.stdout.write(self.style.SUCCESS(f'  [OK] {app} → {db_alias}'))
                except Exception as err:
                    self.stdout.write(self.style.WARNING(f'  [WARN] {app} → {db_alias}: {err}'))

            # Mark db_migrated
            if not tenant.db_migrated:
                tenant.db_migrated = True
                tenant.save(update_fields=['db_migrated'])

        self.stdout.write(self.style.SUCCESS('\n✓ migrate_tenants completed successfully.'))

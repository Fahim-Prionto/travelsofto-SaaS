"""
apps/tenants/management/commands/fix_tenant_domains.py

Fixes stale TenantDomain records that were created with localhost:PORT
by updating them to use the current BASE_DOMAIN from settings.

Usage (run on cPanel after updating .env):
    python manage.py fix_tenant_domains
    python manage.py fix_tenant_domains --dry-run
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.tenants.models import Tenant, TenantDomain


class Command(BaseCommand):
    help = 'Fix stale TenantDomain records that still contain localhost or wrong domain.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without actually saving.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        raw_base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000')

        # Strip protocol (http:// or https://) and trailing slashes that may
        # have been accidentally included in the .env value
        clean_base = raw_base_domain \
            .replace('https://', '') \
            .replace('http://', '') \
            .strip('/')
        # Also strip port for the domain record (subdomain.softobro.com not subdomain.softobro.com:443)
        clean_base = clean_base.split(':')[0]

        self.stdout.write(f'BASE_DOMAIN (raw)  = {raw_base_domain}')
        self.stdout.write(f'BASE_DOMAIN (clean) = {clean_base}')
        self.stdout.write(f'Scanning all subdomain TenantDomain records...\n')

        fixed = 0
        for tenant in Tenant.objects.all():
            expected_domain = f'{tenant.slug}.{clean_base}'

            # Find the subdomain record(s) for this tenant
            subdomain_records = TenantDomain.objects.filter(
                tenant=tenant,
                domain_type=TenantDomain.DomainType.SUBDOMAIN,
            )

            if not subdomain_records.exists():
                # Auto-create missing subdomain record
                if not dry_run:
                    TenantDomain.objects.create(
                        tenant=tenant,
                        domain=expected_domain,
                        domain_type=TenantDomain.DomainType.SUBDOMAIN,
                        is_primary=True,
                        status=TenantDomain.Status.ACTIVE,
                    )
                self.stdout.write(
                    self.style.WARNING(f'[CREATE] {tenant.slug} → {expected_domain}')
                )
                fixed += 1
                continue

            for record in subdomain_records:
                # Fix if it contains localhost or wrong domain
                needs_fix = (
                    'localhost' in record.domain or
                    '127.0.0.1' in record.domain or
                    record.domain != expected_domain
                )
                if needs_fix:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[FIX] {tenant.slug}: "{record.domain}" → "{expected_domain}"'
                        )
                    )
                    if not dry_run:
                        record.domain = expected_domain
                        record.status = TenantDomain.Status.ACTIVE
                        record.is_primary = True
                        record.save(update_fields=['domain', 'status', 'is_primary'])
                    fixed += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'[OK] {tenant.slug}: {record.domain}')
                    )

        if dry_run:
            self.stdout.write(f'\n[DRY RUN] {fixed} record(s) would be fixed.')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Done. Fixed {fixed} TenantDomain record(s).')
            )

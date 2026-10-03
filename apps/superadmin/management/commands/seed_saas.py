"""
apps/superadmin/management/commands/seed_saas.py

Command to seed initial SaaS data:
  - Default Subscription Packages (Starter, Professional, Enterprise)
  - Default Global Settings
  - Initial Super Admin account prompt
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.subscriptions.models import SubscriptionPackage
from apps.tenants.models import GlobalSetting

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial SaaS subscription packages and global platform settings.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding SaaS subscription packages...'))

        # ── Starter Package ───────────────────────────────────────────────────
        pkg_starter, created = SubscriptionPackage.objects.get_or_create(
            package_type=SubscriptionPackage.PackageType.STARTER,
            defaults={
                'name': 'Starter Plan',
                'description': 'Perfect for new travel agencies starting their journey.',
                'monthly_price': Decimal('49.00'),
                'yearly_price': Decimal('470.00'),
                'trial_days': 14,
                'max_users': 100,
                'max_travel_packages': 10,
                'max_visa_services': 5,
                'max_staff': 2,
                'storage_limit_mb': 512,
                'custom_domain': False,
                'advanced_analytics': False,
                'advanced_cms': False,
                'priority_support': False,
                'badge_color': 'secondary',
                'sort_order': 1,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {pkg_starter.name}'))

        # ── Professional Package ───────────────────────────────────────────────
        pkg_pro, created = SubscriptionPackage.objects.get_or_create(
            package_type=SubscriptionPackage.PackageType.PROFESSIONAL,
            defaults={
                'name': 'Professional Plan',
                'description': 'Ideal for growing travel agencies with expanding operations.',
                'monthly_price': Decimal('99.00'),
                'yearly_price': Decimal('950.00'),
                'trial_days': 14,
                'max_users': 1000,
                'max_travel_packages': 50,
                'max_visa_services': 25,
                'max_staff': 10,
                'storage_limit_mb': 2048,
                'custom_domain': True,
                'advanced_analytics': True,
                'advanced_cms': True,
                'priority_support': False,
                'is_recommended': True,
                'badge_color': 'primary',
                'sort_order': 2,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {pkg_pro.name}'))

        # ── Enterprise Package ────────────────────────────────────────────────
        pkg_ent, created = SubscriptionPackage.objects.get_or_create(
            package_type=SubscriptionPackage.PackageType.ENTERPRISE,
            defaults={
                'name': 'Enterprise Plan',
                'description': 'Unlimited power and support for high-volume travel businesses.',
                'monthly_price': Decimal('249.00'),
                'yearly_price': Decimal('2390.00'),
                'trial_days': 30,
                'max_users': -1,
                'max_travel_packages': -1,
                'max_visa_services': -1,
                'max_staff': -1,
                'storage_limit_mb': -1,
                'custom_domain': True,
                'advanced_analytics': True,
                'advanced_cms': True,
                'priority_support': True,
                'white_label': True,
                'api_access': True,
                'badge_color': 'success',
                'sort_order': 3,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {pkg_ent.name}'))

        # ── Seed Global Settings ──────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE('Seeding global platform settings...'))

        default_settings = {
            'platform_name': 'ViserTrip',
            'platform_email': 'support@visertrip.com',
            'currency_symbol': '$',
            'currency_code': 'USD',
            'allow_registration': 'true',
            'trial_period_days': '14',
            'maintenance_mode': 'false',
        }

        for key, value in default_settings.items():
            setting, created = GlobalSetting.objects.get_or_create(
                key=key,
                defaults={'value': value}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Setting created: {key} = {value}'))

        self.stdout.write(self.style.SUCCESS('SaaS initial seed completed successfully!'))

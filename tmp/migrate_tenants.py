import os
import sys
import django

sys.path.insert(0, r'd:\Softobro Main\travel')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from apps.tenants.models import Tenant

tenant_apps = [
    'travel_packages',
    'bookings',
    'bus',
    'visa',
    'payments',
    'destinations',
    'cms',
    'support',
    'coupons',
    'notifications',
    'kyc',
]

for tenant in Tenant.objects.all():
    db_alias = f'tenant_{tenant.slug}'
    settings.DATABASES[db_alias] = tenant.get_db_config()
    print(f"=== Migrating Tenant: {tenant.slug} ({db_alias}) ===")
    
    for app in tenant_apps:
        try:
            connections[db_alias].close()
            call_command('migrate', app, '--database', db_alias, verbosity=1)
            print(f"  [SUCCESS] {app}")
        except Exception as app_e:
            print(f"  [ERROR] {app}: {app_e}")

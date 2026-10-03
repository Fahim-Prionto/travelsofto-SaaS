import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from apps.tenants.models import Tenant
from apps.tenants.provisioning import register_tenant_database

aliases = ['default']
for tenant in Tenant.objects.all():
    aliases.append(register_tenant_database(tenant))

sql_statements = [
    "ALTER TABLE bookings_booking ADD COLUMN IF NOT EXISTS customer_user_id VARCHAR(255) NULL;",
    "ALTER TABLE bookings_booking ADD COLUMN IF NOT EXISTS booked_by_email VARCHAR(255) NULL;",
    "ALTER TABLE bookings_booking ADD COLUMN IF NOT EXISTS booked_by_role VARCHAR(50) NULL;",
    "ALTER TABLE bookings_booking ADD COLUMN IF NOT EXISTS special_requests TEXT NULL;",
]

for db in aliases:
    conn = connections[db]
    print(f"Checking DB: {db}")
    with conn.cursor() as cursor:
        for stmt in sql_statements:
            try:
                cursor.execute(stmt)
                print(f"  Ran: {stmt.strip()}")
            except Exception as e:
                print(f"  Error on {db}: {e}")

print("Done updating schemas!")

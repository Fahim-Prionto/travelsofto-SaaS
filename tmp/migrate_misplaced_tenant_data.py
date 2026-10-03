import os, sys, django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.db import connections
from apps.tenants.models import Tenant

tenant = Tenant.objects.filter(slug='fahim-travel').first()
if not tenant:
    print("Tenant fahim-travel not found")
    sys.exit(1)

db_alias = f'tenant_{tenant.slug}'
settings.DATABASES[db_alias] = tenant.get_db_config()
print(f"Target tenant DB: {db_alias} ({tenant.db_name})")

# Use raw SQL to copy packages
src = connections['default']
dst = connections[db_alias]

# ── Copy travel_packages_travelpackage ──────────────────────────────────
with src.cursor() as cur:
    cur.execute("SELECT id, name, slug, description, short_description, destination_name, travel_date, return_date, duration_days, difficulty, price, discounted_price, currency, total_seats, available_seats, featured_image, included_services, excluded_services, status, is_featured, meta_title, meta_description, view_count, booking_count, created_at, updated_at, uid FROM travel_packages_travelpackage")
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description]

print(f"Found {len(rows)} package(s) in default DB")

with dst.cursor() as cur:
    for row in rows:
        data = dict(zip(columns, row))
        # Check if already exists in tenant DB
        cur.execute("SELECT id FROM travel_packages_travelpackage WHERE slug = %s", [data['slug']])
        if cur.fetchone():
            print(f"  Package '{data['name']}' already exists in tenant DB, skipping")
            continue

        placeholders = ', '.join(['%s'] * len(columns))
        col_names = ', '.join(columns)
        values = [data[c] for c in columns]
        cur.execute(f"INSERT INTO travel_packages_travelpackage ({col_names}) VALUES ({placeholders})", values)
        print(f"  Migrated package: '{data['name']}' (slug: {data['slug']})")

# ── Copy travel_packages_packageimage ──────────────────────────────────
with src.cursor() as src_cur:
    src_cur.execute("SELECT pi.id, pi.caption, pi.sort_order, pi.created_at, pi.image, tp.slug as pkg_slug FROM travel_packages_packageimage pi JOIN travel_packages_travelpackage tp ON pi.package_id = tp.id")
    img_rows = src_cur.fetchall()
    img_cols = [d[0] for d in src_cur.description]

print(f"Found {len(img_rows)} package image(s) in default DB")

with dst.cursor() as cur:
    for row in img_rows:
        data = dict(zip(img_cols, row))
        # Get corresponding package in tenant DB
        cur.execute("SELECT id FROM travel_packages_travelpackage WHERE slug = %s", [data['pkg_slug']])
        pkg_row = cur.fetchone()
        if not pkg_row:
            print(f"  Package for image not found in tenant DB, skipping")
            continue
        pkg_id = pkg_row[0]

        cur.execute("SELECT id FROM travel_packages_packageimage WHERE package_id = %s AND image = %s", [pkg_id, data['image']])
        if cur.fetchone():
            print(f"  Image already exists in tenant DB, skipping")
            continue

        cur.execute(
            "INSERT INTO travel_packages_packageimage (caption, sort_order, created_at, image, package_id) VALUES (%s, %s, %s, %s, %s)",
            [data['caption'], data['sort_order'], data['created_at'], data['image'], pkg_id]
        )
        print(f"  Migrated image '{data['image']}' for package slug '{data['pkg_slug']}'")

# ── Copy cms_herosection ────────────────────────────────────────────────
try:
    with src.cursor() as src_cur:
        src_cur.execute("SELECT * FROM cms_herosection")
        hero_rows = src_cur.fetchall()
        hero_cols = [d[0] for d in src_cur.description]

    print(f"Found {len(hero_rows)} hero section(s) in default DB")

    with dst.cursor() as cur:
        for row in hero_rows:
            data = dict(zip(hero_cols, row))
            cur.execute("SELECT id FROM cms_herosection LIMIT 1")
            if cur.fetchone():
                print(f"  HeroSection already exists in tenant DB, skipping")
                continue
            placeholders = ', '.join(['%s'] * len(hero_cols))
            col_names = ', '.join(hero_cols)
            values = [data[c] for c in hero_cols]
            cur.execute(f"INSERT INTO cms_herosection ({col_names}) VALUES ({placeholders})", values)
            print(f"  Migrated HeroSection: '{data.get('title', '')}'")
except Exception as e:
    print(f"  HeroSection migration skipped: {e}")

print("\n=== FINAL STATUS IN TENANT DB ===")
with dst.cursor() as cur:
    cur.execute("SELECT id, name, status, slug FROM travel_packages_travelpackage")
    print("Packages:", cur.fetchall())
    cur.execute("SELECT id, package_id, image FROM travel_packages_packageimage")
    print("Images:", cur.fetchall())

print("\nDone!")

import os, sys, django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from apps.tenants.models import Tenant
from apps.travel_packages.models import TravelPackage, PackageImage
from apps.visa.models import VisaService, VisaApplication
from apps.bookings.models import Booking
from apps.cms.models import HeroSection

print("=== DEFAULT DB ===")
print("TravelPackage:", list(TravelPackage.objects.using('default').values('id', 'name', 'status', 'slug')))
print("PackageImage:", list(PackageImage.objects.using('default').values('id', 'package_id')))
print("VisaService:", list(VisaService.objects.using('default').values('id', 'name')))
print("Booking:", list(Booking.objects.using('default').values('id', 'booking_code')))
print("HeroSection:", list(HeroSection.objects.using('default').values('id', 'title')))

for t in Tenant.objects.all():
    db_alias = f'tenant_{t.slug}'
    settings.DATABASES[db_alias] = t.get_db_config()
    print(f"\n=== TENANT DB ({db_alias} -> {t.db_name}) ===")
    print("TravelPackage:", list(TravelPackage.objects.using(db_alias).values('id', 'name', 'status', 'slug')))
    print("PackageImage:", list(PackageImage.objects.using(db_alias).values('id', 'package_id')))
    print("VisaService:", list(VisaService.objects.using(db_alias).values('id', 'name')))
    print("Booking:", list(Booking.objects.using(db_alias).values('id', 'booking_code')))
    print("HeroSection:", list(HeroSection.objects.using(db_alias).values('id', 'title')))

"""
apps/tenants/directory_urls.py

URL conf for path-based agency directory access.
Mounted at: /a/<agency_slug>/

Mirrors the public_urls.py routes so each agency's website is equally
accessible via:
  - Subdomain:  https://{slug}.softobro.com/
  - Directory:  https://travel.softobro.com/a/{slug}/
"""
from django.urls import path
from . import directory_views

app_name = 'directory'

urlpatterns = [
    # Agency Website Home
    path('', directory_views.agency_home, name='home'),
    path('packages/', directory_views.agency_packages, name='packages'),
    path('packages/<slug:slug>/', directory_views.agency_package_detail, name='package_detail'),
    path('visa-services/', directory_views.agency_visa, name='visa_services'),
    path('about/', directory_views.agency_about, name='about'),
    path('contact/', directory_views.agency_contact, name='contact'),
]

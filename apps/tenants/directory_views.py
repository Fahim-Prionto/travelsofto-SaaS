"""
apps/tenants/directory_views.py

Path-based Agency Directory Views.

Handles requests of the form:
    /a/<agency_slug>/           → agency one-page landing website
    /a/<agency_slug>/packages/  → packages list (kept for deep links)
    etc.
"""
import logging
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django.conf import settings

from apps.tenants.models import Tenant
from apps.tenants.routers import set_tenant_db

logger = logging.getLogger(__name__)


def _resolve_tenant(agency_slug):
    """Look up an active Tenant by slug. Returns the Tenant or None."""
    return Tenant.objects.filter(slug=agency_slug, status__in=[
        Tenant.Status.ACTIVE, Tenant.Status.TRIAL
    ]).first()


def _setup_tenant_on_request(request, tenant):
    """Attach tenant to request and register the tenant DB."""
    request.tenant = tenant
    db_alias = f'tenant_{tenant.slug}'
    if db_alias not in settings.DATABASES:
        settings.DATABASES[db_alias] = tenant.get_db_config()
    set_tenant_db(db_alias)
    return db_alias


def _load_cms(db_alias):
    """Load all CMS content from the tenant's database."""
    from apps.cms.models import HeroSection, AboutSection, WebsiteSetting, Testimonial

    hero = HeroSection.objects.using(db_alias).filter(is_active=True).first()
    about = AboutSection.objects.using(db_alias).filter(is_active=True).first()
    testimonials = Testimonial.objects.using(db_alias).filter(is_active=True)[:6]

    def ws(key, default=''):
        return WebsiteSetting.objects.using(db_alias).filter(key=key).values_list('value', flat=True).first() or default

    settings_map = {
        'primary_color':   ws('primary_color', '#0057e7'),
        'contact_phone':   ws('contact_phone'),
        'contact_email':   ws('contact_email'),
        'contact_address': ws('contact_address'),
        'map_embed_url':   ws('map_embed_url'),
        'meta_title':      ws('meta_title'),
        'meta_description':ws('meta_description'),
        'about_tagline':   ws('about_tagline'),
    }
    return hero, about, testimonials, settings_map


def _load_packages(db_alias):
    """Load active tour packages from the tenant's database."""
    from apps.travel_packages.models import TravelPackage
    try:
        return TravelPackage.objects.using(db_alias).filter(
            status=TravelPackage.Status.ACTIVE
        ).order_by('-is_featured', '-created_at')[:12]
    except Exception:
        return []


def _load_visa_services(db_alias):
    """Load active visa services from the tenant's database."""
    from apps.visa.models import VisaService
    try:
        return VisaService.objects.using(db_alias).filter(is_active=True).order_by('-is_featured', '-created_at')[:8]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LANDING PAGE – single page, all sections
# ─────────────────────────────────────────────────────────────────────────────
def agency_home(request, agency_slug):
    """
    Directory Landing Page: /a/<agency_slug>/
    Renders a beautiful full one-page agency website with:
      Hero → Stats → Packages → Visa Services → About → Testimonials → Contact
    All content is pulled live from the agency's tenant database.
    """
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")

    db_alias = _setup_tenant_on_request(request, tenant)

    hero, about, testimonials, cms = _load_cms(db_alias)
    packages = _load_packages(db_alias)
    visa_services = _load_visa_services(db_alias)

    site_url = getattr(settings, 'SITE_URL', '')
    base_domain = getattr(settings, 'BASE_DOMAIN', '')

    context = {
        'tenant': tenant,
        'agency_slug': agency_slug,
        'hero': hero,
        'about': about,
        'testimonials': testimonials,
        'cms': cms,
        'packages': packages,
        'visa_services': visa_services,
        'packages_count': len(packages),
        'visa_count': len(visa_services),
        'site_url': site_url,
        'base_domain': base_domain,
        'directory_base': f'{site_url}/a/{agency_slug}',
    }
    return render(request, 'website/agency_landing.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-pages (kept for direct deep-linking from the landing page)
# ─────────────────────────────────────────────────────────────────────────────
def agency_packages(request, agency_slug):
    """Directory Packages: /a/<agency_slug>/packages/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")
    _setup_tenant_on_request(request, tenant)
    from apps.tenants.public_views import packages_list
    return packages_list(request)


def agency_package_detail(request, agency_slug, slug):
    """Directory Package Detail: /a/<agency_slug>/packages/<slug>/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")
    _setup_tenant_on_request(request, tenant)
    from apps.tenants.public_views import package_detail
    return package_detail(request, slug=slug)


def agency_visa(request, agency_slug):
    """Directory Visa Services: /a/<agency_slug>/visa-services/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")
    _setup_tenant_on_request(request, tenant)
    from apps.tenants.public_views import visa_list
    return visa_list(request)


def agency_about(request, agency_slug):
    """Directory About: /a/<agency_slug>/about/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")
    _setup_tenant_on_request(request, tenant)
    from apps.tenants.public_views import about
    return about(request)


def agency_contact(request, agency_slug):
    """Directory Contact: /a/<agency_slug>/contact/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        raise Http404("Agency not found or not active.")
    _setup_tenant_on_request(request, tenant)
    from apps.tenants.public_views import contact
    return contact(request)

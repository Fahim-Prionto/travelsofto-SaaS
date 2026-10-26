"""
apps/tenants/directory_views.py

Path-based Agency Directory Views.

Handles requests of the form:
    /a/<agency_slug>/           → agency home
    /a/<agency_slug>/packages/  → packages
    etc.

Resolves the tenant from the URL slug, temporarily sets the tenant on the
request object, then delegates to the existing public_views functions so
there is no code duplication.
"""
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings

from apps.tenants.models import Tenant
from apps.tenants.routers import set_tenant_db

logger = logging.getLogger(__name__)


def _resolve_tenant(agency_slug):
    """Look up a Tenant by slug. Returns the Tenant or None."""
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


def agency_home(request, agency_slug):
    """
    Directory Home: /a/<agency_slug>/
    Shows the agency's own website homepage.
    """
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    # Delegate to existing public home view (it checks request.tenant)
    from apps.tenants.public_views import home
    return home(request)


def agency_packages(request, agency_slug):
    """Directory Packages: /a/<agency_slug>/packages/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    from apps.tenants.public_views import packages_list
    return packages_list(request)


def agency_package_detail(request, agency_slug, slug):
    """Directory Package Detail: /a/<agency_slug>/packages/<slug>/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    from apps.tenants.public_views import package_detail
    return package_detail(request, slug=slug)


def agency_visa(request, agency_slug):
    """Directory Visa Services: /a/<agency_slug>/visa-services/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    from apps.tenants.public_views import visa_list
    return visa_list(request)


def agency_about(request, agency_slug):
    """Directory About: /a/<agency_slug>/about/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    from apps.tenants.public_views import about
    return about(request)


def agency_contact(request, agency_slug):
    """Directory Contact: /a/<agency_slug>/contact/"""
    tenant = _resolve_tenant(agency_slug)
    if not tenant:
        from django.http import Http404
        raise Http404("Agency not found or not active.")

    _setup_tenant_on_request(request, tenant)

    from apps.tenants.public_views import contact
    return contact(request)

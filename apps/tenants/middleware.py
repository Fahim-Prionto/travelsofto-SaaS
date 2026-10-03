"""
apps/tenants/middleware.py

Tenant Identification Middleware.

On every request:
  1. Extract the hostname from the request.
  2. Lookup the matching TenantDomain in the main database.
  3. Load the Tenant object and its database configuration.
  4. Register the tenant database in Django's DATABASES dict (if not already done).
  5. Set the thread-local tenant DB alias so the router can direct queries.
  6. Attach the tenant object to request.tenant for use in views/templates.

If no tenant domain matches (e.g. superadmin paths), tenant context is None.
"""
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from apps.tenants.routers import set_tenant_db

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):

    def process_request(self, request):
        # Clear any previous tenant context
        set_tenant_db(None)
        request.tenant = None

        hostname = request.get_host().split(':')[0].lower()

        # Skip tenant resolution for super admin paths
        superadmin_prefix = getattr(settings, 'SUPERADMIN_URL_PREFIX', 'superadmin')
        if request.path.startswith(f'/{superadmin_prefix}/'):
            return None

        # 1. Fallback for authenticated user if on localhost or no domain match
        try:
            from apps.tenants.models import Tenant, TenantDomain

            tenant = None

            # Domain lookup (supports custom domains & exact subdomains)
            domain_obj = TenantDomain.objects.select_related('tenant').filter(
                domain__iexact=hostname
            ).first()

            if domain_obj:
                tenant = domain_obj.tenant
            else:
                # Subdomain slug fallback (e.g. fahim-travel.localhost -> slug 'fahim-travel')
                base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000').split(':')[0].lower()
                if '.' in hostname and (hostname.endswith(f'.{base_domain}') or hostname.endswith('.localhost')):
                    subdomain_prefix = hostname.split('.')[0]
                    tenant = Tenant.objects.filter(slug=subdomain_prefix).first()
                    if tenant:
                        TenantDomain.objects.get_or_create(
                            tenant=tenant,
                            domain=hostname,
                            defaults={
                                'domain_type': TenantDomain.DomainType.SUBDOMAIN,
                                'status': TenantDomain.Status.ACTIVE,
                                'is_primary': True,
                            }
                        )

            # Fallback to logged in user's tenant if hostname is localhost/127.0.0.1 or no domain matched
            if not tenant and hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'tenant_id', None):
                tenant = Tenant.objects.filter(slug=request.user.tenant_id).first()

            if tenant:
                request.tenant = tenant

                # Register tenant database dynamically
                db_alias = f'tenant_{tenant.slug}'
                if db_alias not in settings.DATABASES:
                    settings.DATABASES[db_alias] = tenant.get_db_config()

                set_tenant_db(db_alias)
                logger.debug(f'Tenant resolved: {tenant.slug} → db: {db_alias}')

        except Exception as e:
            logger.error(f'Error resolving tenant domain for {hostname}: {e}')

        return None

    def process_response(self, request, response):
        # Always clear tenant context after response
        set_tenant_db(None)
        return response

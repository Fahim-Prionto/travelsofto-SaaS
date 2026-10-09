"""
apps/tenants/routers.py

Multi-Database Router for ViserTrip.

Routing Strategy:
  - All 'main' app models (accounts, tenants, subscriptions, domains,
    superadmin) always use the 'default' (main) database.
  - When a request is processing in the context of a tenant, all other
    model reads/writes are routed to that tenant's database.
  - The current tenant database alias is stored in a thread-local variable
    set by TenantMiddleware.
"""
import threading

_thread_locals = threading.local()

# Apps that always stay in the main database
MAIN_DB_APPS = {
    'accounts',
    'account',
    'socialaccount',
    'tenants',
    'subscriptions',
    'domains',
    'superadmin',
    'admin',
    'auth',
    'contenttypes',
    'sessions',
    'sites',
}

# These models are inside the 'tenants' app but must route to their isolated tenant DB
TENANT_SPECIFIC_MODELS = {
    'agencyagent',
    'agencycompany',
    'agencyposition',
    'selectiongrade',
    'visalot',
    'candidate',
    'candidatepayment',
    'candidatedocument',
    'requisition',
    'accountheadgroup',
    'chartofaccount',
    'accountvoucher',
    'dailymovement',
    'leavesubmission',
    'officeexpense',
}

def set_tenant_db(db_alias: str | None):
    """Set the current tenant database alias for this thread."""
    _thread_locals.tenant_db = db_alias


def get_tenant_db() -> str | None:
    """Get the current tenant database alias for this thread."""
    return getattr(_thread_locals, 'tenant_db', None)


class TenantDatabaseRouter:
    """
    Routes database queries to the appropriate database.

    - Models in MAIN_DB_APPS (excluding TENANT_SPECIFIC_MODELS) → always 'default'
    - All other models → tenant_db (if set) or 'default'
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in MAIN_DB_APPS:
            if model._meta.app_label == 'tenants' and model._meta.model_name in TENANT_SPECIFIC_MODELS:
                tenant_db = get_tenant_db()
                return tenant_db or 'default'
            return 'default'
        tenant_db = get_tenant_db()
        return tenant_db or 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in MAIN_DB_APPS:
            if model._meta.app_label == 'tenants' and model._meta.model_name in TENANT_SPECIFIC_MODELS:
                tenant_db = get_tenant_db()
                return tenant_db or 'default'
            return 'default'
        tenant_db = get_tenant_db()
        return tenant_db or 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations within same database
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'default':
            if app_label == 'tenants' and model_name in TENANT_SPECIFIC_MODELS:
                return False
            # Prevent tenant apps from migrating to the default database (public schema)
            tenant_apps = {'travel_packages', 'visa', 'bookings', 'payments', 'destinations', 'cms', 'support', 'coupons', 'notifications', 'kyc', 'bus', 'analytics', 'reviews'}
            if app_label in tenant_apps:
                return False
            return True
        else:
            if app_label == 'tenants' and model_name in TENANT_SPECIFIC_MODELS:
                return True
            return app_label not in MAIN_DB_APPS

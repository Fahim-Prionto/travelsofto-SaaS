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


def set_tenant_db(db_alias: str | None):
    """Set the current tenant database alias for this thread."""
    _thread_locals.tenant_db = db_alias


def get_tenant_db() -> str | None:
    """Get the current tenant database alias for this thread."""
    return getattr(_thread_locals, 'tenant_db', None)


class TenantDatabaseRouter:
    """
    Routes database queries to the appropriate database.

    - Models in MAIN_DB_APPS → always 'default'
    - All other models → tenant_db (if set) or 'default'
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in MAIN_DB_APPS:
            return 'default'
        tenant_db = get_tenant_db()
        return tenant_db or 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in MAIN_DB_APPS:
            return 'default'
        tenant_db = get_tenant_db()
        return tenant_db or 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations within same database
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'default':
            return True
        else:
            return app_label not in MAIN_DB_APPS

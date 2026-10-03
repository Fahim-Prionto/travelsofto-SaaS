"""
apps/tenants/context_processors.py

Injects the current tenant into all templates.
"""


def current_tenant(request):
    return {
        'current_tenant': getattr(request, 'tenant', None),
    }

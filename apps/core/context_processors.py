"""
apps/core/context_processors.py

Injects global platform settings into all templates.
"""
from django.conf import settings


def platform_settings(request):
    return {
        'PLATFORM_NAME': getattr(settings, 'PLATFORM_NAME', 'Softobro Travel'),
        'BASE_DOMAIN': getattr(settings, 'BASE_DOMAIN', 'localhost:8000'),
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }

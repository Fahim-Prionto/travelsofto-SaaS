"""
ViserTrip - Main URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin (default, for dev purposes)
    path('django-admin/', admin.site.urls),

    # Super Admin Panel
    path(f'{settings.SUPERADMIN_URL_PREFIX}/', include('apps.superadmin.urls', namespace='superadmin')),

    # Authentication (shared)
    path('auth/', include('apps.accounts.urls', namespace='accounts')),

    # API endpoints
    path('api/v1/', include('config.api_urls')),

    # Tenant/Admin Panel - accessed via subdomain routing
    path('admin-panel/', include('apps.tenants.admin_urls', namespace='admin_panel')),

    # Customer-facing routes (handled by tenant middleware)
    path('', include('apps.tenants.public_urls', namespace='public')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

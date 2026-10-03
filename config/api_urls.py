"""
ViserTrip API URL Configuration (v1)
"""
from django.urls import path, include

urlpatterns = [
    path('accounts/', include('apps.accounts.api_urls')),
    path('tenants/', include('apps.tenants.api_urls')),
    path('subscriptions/', include('apps.subscriptions.api_urls')),
    path('packages/', include('apps.travel_packages.api_urls')),
    path('destinations/', include('apps.destinations.api_urls')),
    path('visa/', include('apps.visa.api_urls')),
    path('bookings/', include('apps.bookings.api_urls')),
    path('payments/', include('apps.payments.api_urls')),
    path('notifications/', include('apps.notifications.api_urls')),
    path('support/', include('apps.support.api_urls')),
]

from django.urls import path
from . import public_views, customer_views

app_name = 'public'

urlpatterns = [
    # Public Agency Website
    path('', public_views.home, name='home'),
    path('packages/', public_views.packages_list, name='packages'),
    path('packages/<slug:slug>/', public_views.package_detail, name='package_detail'),
    path('packages/<slug:slug>/book/', public_views.package_book, name='package_book'),
    path('visa-services/', public_views.visa_list, name='visa_services'),
    path('about/', public_views.about, name='about'),
    path('contact/', public_views.contact, name='contact'),

    # Customer Portal
    path('my-portal/', customer_views.customer_dashboard, name='customer_dashboard'),
    path('my-portal/bookings/', customer_views.customer_bookings, name='customer_bookings'),
    path('my-portal/bus-bookings/', customer_views.customer_bus_bookings, name='customer_bus_bookings'),
    path('my-portal/air-bookings/', customer_views.customer_air_bookings, name='customer_air_bookings'),
    path('my-portal/visa-applications/', customer_views.customer_visa_history, name='customer_visa_history'),
    path('my-portal/payments/', customer_views.customer_payments, name='customer_payments'),
    path('my-portal/support/', customer_views.customer_support, name='customer_support'),
    path('my-portal/profile/', customer_views.customer_profile, name='customer_profile'),
]

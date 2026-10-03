from django.urls import path
from . import api_views

app_name = 'bookings_api'

urlpatterns = [
    path('create/', api_views.BookingCreateAPIView.as_view(), name='api_booking_create'),
    path('my-bookings/', api_views.BookingListAPIView.as_view(), name='api_my_bookings'),
]

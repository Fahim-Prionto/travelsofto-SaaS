"""
apps/bookings/api_views.py
"""
from rest_framework import generics, permissions
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer


class BookingCreateAPIView(generics.CreateAPIView):
    """API endpoint to create travel package booking."""
    serializer_class = BookingSerializer
    permission_classes = [permissions.AllowAny]


class BookingListAPIView(generics.ListAPIView):
    """API endpoint to list customer bookings."""
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        db = f'tenant_{self.request.tenant.slug}' if getattr(self.request, 'tenant', None) else 'default'
        try:
            return Booking.objects.using(db).filter(customer_email=self.request.user.email)
        except Exception:
            return Booking.objects.none()

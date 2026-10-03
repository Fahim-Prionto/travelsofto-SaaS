"""
apps/bookings/serializers.py
"""
from rest_framework import serializers
from apps.bookings.models import Booking


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            'booking_code', 'customer_name', 'customer_email', 'customer_mobile',
            'package', 'travel_date', 'number_of_travelers', 'unit_price',
            'total_amount', 'status', 'payment_status', 'booked_at'
        ]
        read_only_fields = ['booking_code', 'total_amount', 'status', 'payment_status', 'booked_at']

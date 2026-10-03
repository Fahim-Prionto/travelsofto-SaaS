"""
apps/bus/models.py

Bus Ticket system models for TENANT databases.
Covers:
  - BusOperator (bus company)
  - BusRoute (from/to city)
  - BusSchedule (departure, seats, price)
  - BusBooking (customer/staff/ambassador/admin booking)
"""
import uuid
import random
import string
from django.db import models
from django.utils import timezone


class BusOperator(models.Model):
    """Bus transport company / operator."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True, blank=True)
    logo = models.ImageField(upload_to='bus/operators/', blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Bus Operator'

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = 'BUS-' + ''.join(random.choices(string.digits, k=4))
        super().save(*args, **kwargs)


class BusRoute(models.Model):
    """A route between two cities operated by a bus company."""

    operator = models.ForeignKey(
        BusOperator, on_delete=models.CASCADE, related_name='routes'
    )
    from_city = models.CharField(max_length=150)
    to_city = models.CharField(max_length=150)
    distance_km = models.PositiveIntegerField(default=0)
    estimated_duration = models.CharField(max_length=50, blank=True, help_text='e.g. 3h 30m')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['from_city', 'to_city']
        verbose_name = 'Bus Route'
        unique_together = [['operator', 'from_city', 'to_city']]

    def __str__(self):
        return f"{self.operator.name}: {self.from_city} → {self.to_city}"


class BusSchedule(models.Model):
    """A scheduled bus trip on a specific route."""

    class SeatClass(models.TextChoices):
        ECONOMY = 'economy', 'Economy'
        BUSINESS = 'business', 'Business'
        AC = 'ac', 'AC Sleeper'
        NON_AC = 'non_ac', 'Non-AC'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    route = models.ForeignKey(BusRoute, on_delete=models.CASCADE, related_name='schedules')
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    seat_class = models.CharField(max_length=20, choices=SeatClass.choices, default=SeatClass.ECONOMY)
    total_seats = models.PositiveIntegerField(default=40)
    available_seats = models.PositiveIntegerField(default=40)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['departure_time']
        verbose_name = 'Bus Schedule'

    def __str__(self):
        return f"{self.route} | {self.departure_time.strftime('%Y-%m-%d %H:%M')} ({self.get_seat_class_display()})"


class BusBooking(models.Model):
    """A bus ticket booking made by customer/staff/ambassador/admin."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    class BookedByRole(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        STAFF = 'staff', 'Staff'
        AMBASSADOR = 'ambassador', 'Ambassador'
        ADMIN = 'admin', 'Admin'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    booking_code = models.CharField(max_length=20, unique=True, blank=True)

    # Relations
    schedule = models.ForeignKey(BusSchedule, on_delete=models.PROTECT, related_name='bookings')

    # Passenger Info
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_mobile = models.CharField(max_length=20, blank=True)
    passenger_count = models.PositiveIntegerField(default=1)
    seat_numbers = models.CharField(max_length=100, blank=True, help_text='e.g. A1,A2,B3')

    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)

    # Booking origin
    booked_by_role = models.CharField(max_length=15, choices=BookedByRole.choices, default=BookedByRole.CUSTOMER)
    booked_by_email = models.EmailField(blank=True, help_text='Email of staff/ambassador who made booking')

    # Notes
    special_requests = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Timestamps
    booked_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-booked_at']
        verbose_name = 'Bus Booking'

    def __str__(self):
        return f"{self.booking_code} – {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = 'BUS' + ''.join(random.choices(string.digits, k=7))
        if not self.total_amount:
            self.total_amount = (self.unit_price * self.passenger_count) - self.discount_amount
        super().save(*args, **kwargs)

    def confirm(self):
        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at'])

    def cancel(self, reason=''):
        self.status = self.Status.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

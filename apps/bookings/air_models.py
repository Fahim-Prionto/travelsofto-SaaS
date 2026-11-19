"""
apps/bookings/air_models.py

Air Ticket models for TENANT databases.
Covers:
  - Airline
  - FlightRoute
  - FlightSchedule
  - AirTicketBooking
"""
import uuid
import random
import string
from django.db import models
from django.utils import timezone


class Airline(models.Model):
    """Airline company."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True, blank=True, help_text='IATA code e.g. BG, BS')
    logo = models.ImageField(upload_to='airlines/logos/', blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Airline'

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = 'AL' + ''.join(random.choices(string.ascii_uppercase, k=2))
        super().save(*args, **kwargs)


class FlightRoute(models.Model):
    """A flight route between two airports/cities."""

    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='routes')
    flight_number = models.CharField(max_length=20)
    from_city = models.CharField(max_length=150)
    from_airport_code = models.CharField(max_length=5, blank=True, help_text='IATA e.g. DAC')
    to_city = models.CharField(max_length=150)
    to_airport_code = models.CharField(max_length=5, blank=True, help_text='e.g. DXB')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['from_city', 'to_city']
        verbose_name = 'Flight Route'
        unique_together = [['airline', 'flight_number']]

    def __str__(self):
        return f"{self.airline.code}{self.flight_number}: {self.from_city} → {self.to_city}"


class FlightSchedule(models.Model):
    """A scheduled flight on a specific route."""

    class CabinClass(models.TextChoices):
        ECONOMY = 'economy', 'Economy'
        PREMIUM_ECONOMY = 'premium_economy', 'Premium Economy'
        BUSINESS = 'business', 'Business'
        FIRST = 'first', 'First Class'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    route = models.ForeignKey(FlightRoute, on_delete=models.CASCADE, related_name='schedules')
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    cabin_class = models.CharField(max_length=20, choices=CabinClass.choices, default=CabinClass.ECONOMY)
    total_seats = models.PositiveIntegerField(default=150)
    available_seats = models.PositiveIntegerField(default=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    baggage_allowance = models.CharField(max_length=50, blank=True, help_text='e.g. 23kg')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['departure_datetime']
        verbose_name = 'Flight Schedule'

    def __str__(self):
        return f"{self.route} | {self.departure_datetime.strftime('%Y-%m-%d %H:%M')} ({self.get_cabin_class_display()})"


class AirTicketBooking(models.Model):
    """An air ticket booking — manual entry, B2B or B2C, with optional ticket attachment and invoice."""

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

    class CustomerType(models.TextChoices):
        B2C = 'b2c', 'B2C (Direct Customer)'
        B2B = 'b2b', 'B2B (Agency Agent)'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    booking_code = models.CharField(max_length=20, unique=True, blank=True)

    # ── Flight Info (manual — no schedule FK required) ─────────────────────
    airline_name = models.CharField(max_length=200, blank=True, help_text='e.g. Biman Bangladesh, Emirates')
    flight_number = models.CharField(max_length=30, blank=True, help_text='e.g. BG401')
    flight_date = models.DateField(null=True, blank=True, help_text='Departure date')
    from_city = models.CharField(max_length=150, blank=True)
    to_city = models.CharField(max_length=150, blank=True)
    # Optional link to a pre-configured schedule (kept for backward compat)
    schedule = models.ForeignKey(
        FlightSchedule, on_delete=models.SET_NULL,
        related_name='bookings', null=True, blank=True
    )

    # ── Customer Type ──────────────────────────────────────────────────────
    customer_type = models.CharField(
        max_length=5, choices=CustomerType.choices, default=CustomerType.B2C
    )
    # B2B fields (denormalised — cross-DB safe)
    b2b_agent_id = models.IntegerField(null=True, blank=True)
    b2b_agent_name = models.CharField(max_length=255, blank=True)
    b2b_agent_code = models.CharField(max_length=50, blank=True)

    # ── Passenger Info ─────────────────────────────────────────────────────
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_mobile = models.CharField(max_length=20, blank=True)
    passenger_count = models.PositiveIntegerField(default=1)
    passport_number = models.CharField(max_length=50, blank=True)
    pnr_number = models.CharField(max_length=20, blank=True)

    # ── Pricing ────────────────────────────────────────────────────────────
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Ticket Attachment (optional) ───────────────────────────────────────
    ticket_file = models.FileField(upload_to='air_tickets/', null=True, blank=True)

    # ── Invoice ────────────────────────────────────────────────────────────
    invoice_number = models.CharField(max_length=30, blank=True)
    invoice_generated = models.BooleanField(default=False)

    # ── Status ─────────────────────────────────────────────────────────────
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)

    # ── Booking origin ─────────────────────────────────────────────────────
    booked_by_role = models.CharField(max_length=15, choices=BookedByRole.choices, default=BookedByRole.ADMIN)
    booked_by_email = models.EmailField(blank=True)

    # ── Notes ──────────────────────────────────────────────────────────────
    special_requests = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    booked_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-booked_at']
        verbose_name = 'Air Ticket Booking'

    def __str__(self):
        return f"{self.booking_code} – {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = 'AIR' + ''.join(random.choices(string.digits, k=7))
        if not self.invoice_number and self.invoice_generated:
            self.invoice_number = 'INV-AIR-' + ''.join(random.choices(string.digits, k=6))
        # Auto-calc total
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

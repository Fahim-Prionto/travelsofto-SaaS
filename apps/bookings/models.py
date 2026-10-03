"""
apps/bookings/models.py

Booking models for TENANT databases.
"""
import uuid
import random
import string
from django.db import models
from django.utils import timezone


class Booking(models.Model):
    """A travel package booking made by a customer."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        ONGOING = 'ongoing', 'Ongoing'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    booking_code = models.CharField(max_length=20, unique=True)

    # ── Customer ───────────────────────────────────────────────────────────────
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255)
    customer_mobile = models.CharField(max_length=20, blank=True)
    customer_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_bookings',
        db_constraint=False,
    )

    # ── Booked By ───────────────────────────────────────────────────────────────
    class BookedByRole(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'
        STAFF = 'staff', 'Staff'
        AMBASSADOR = 'ambassador', 'Ambassador'

    booked_by_role = models.CharField(max_length=15, choices=BookedByRole.choices, default=BookedByRole.CUSTOMER)
    booked_by_email = models.EmailField(blank=True)

    # ── Package ────────────────────────────────────────────────────────────────
    package = models.ForeignKey(
        'travel_packages.TravelPackage',
        on_delete=models.PROTECT,
        related_name='bookings',
    )
    travel_date = models.DateField()
    return_date = models.DateField(blank=True, null=True)
    number_of_travelers = models.PositiveIntegerField(default=1)

    # ── Pricing ────────────────────────────────────────────────────────────────
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=50, blank=True)

    # ── Status ─────────────────────────────────────────────────────────────────
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)

    # ── Notes ──────────────────────────────────────────────────────────────────
    special_requests = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    booked_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-booked_at']

    def __str__(self):
        return f'{self.booking_code} – {self.customer_name}'

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = 'BK' + ''.join(random.choices(string.digits, k=8))
        if not self.total_amount:
            self.total_amount = (self.unit_price * self.number_of_travelers) - self.discount_amount
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

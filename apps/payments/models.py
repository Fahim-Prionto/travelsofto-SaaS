"""
apps/payments/models.py

Payment and Transaction models for TENANT databases.
"""
import uuid
from decimal import Decimal
from django.db import models


class Payment(models.Model):
    """A payment made by a customer for a booking or visa application."""

    class PaymentType(models.TextChoices):
        BOOKING = 'booking', 'Booking Payment'
        VISA = 'visa', 'Visa Application Payment'
        WALLET_TOPUP = 'wallet_topup', 'Wallet Top-up'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
        PARTIAL_REFUND = 'partial_refund', 'Partial Refund'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    transaction_id = models.CharField(max_length=255, unique=True)

    # ── Customer ───────────────────────────────────────────────────────────────
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255, blank=True)

    # ── Reference ──────────────────────────────────────────────────────────────
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    reference_id = models.CharField(max_length=50, blank=True, help_text='Booking code or Visa application code')

    # ── Amount ─────────────────────────────────────────────────────────────────
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='USD')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # ── Method & Status ────────────────────────────────────────────────────────
    payment_method = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # ── Gateway ────────────────────────────────────────────────────────────────
    gateway_name = models.CharField(max_length=50, blank=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_id} – {self.customer_email} – ${self.amount}'

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            import random, string
            self.transaction_id = 'TXN' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        super().save(*args, **kwargs)

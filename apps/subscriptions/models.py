"""
apps/subscriptions/models.py

SaaS Subscription Package and Subscription management.
All stored in the MAIN database.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings


class SubscriptionPackage(models.Model):
    """
    SaaS pricing plans created by the Super Admin.
    Defines feature limits, pricing, and trial periods.
    """

    class PackageType(models.TextChoices):
        STARTER = 'starter', 'Starter'
        PROFESSIONAL = 'professional', 'Professional'
        ENTERPRISE = 'enterprise', 'Enterprise'
        CUSTOM = 'custom', 'Custom'

    # ── Identity ───────────────────────────────────────────────────────────────
    name = models.CharField(max_length=100)
    package_type = models.CharField(max_length=20, choices=PackageType.choices, default=PackageType.STARTER)
    description = models.TextField(blank=True)
    badge_color = models.CharField(max_length=20, default='primary')

    # ── Pricing ────────────────────────────────────────────────────────────────
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    trial_days = models.PositiveIntegerField(default=14)

    # ── Feature Limits (-1 = unlimited) ────────────────────────────────────────
    max_users = models.IntegerField(default=5, help_text='-1 for unlimited')
    max_travel_packages = models.IntegerField(default=10, help_text='-1 for unlimited')
    max_visa_services = models.IntegerField(default=5, help_text='-1 for unlimited')
    max_staff = models.IntegerField(default=2, help_text='-1 for unlimited')
    max_ambassadors = models.IntegerField(default=2, help_text='-1 for unlimited')
    max_bus_routes = models.IntegerField(default=5, help_text='-1 for unlimited')
    max_air_routes = models.IntegerField(default=5, help_text='-1 for unlimited')
    storage_limit_mb = models.IntegerField(default=512, help_text='-1 for unlimited')

    # ── Feature Flags ──────────────────────────────────────────────────────────
    bus_ticket_enabled = models.BooleanField(default=True)
    air_ticket_enabled = models.BooleanField(default=True)
    custom_domain = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    advanced_cms = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    white_label = models.BooleanField(default=False)

    # ── Status ─────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_recommended = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'monthly_price']
        verbose_name = 'Subscription Package'
        verbose_name_plural = 'Subscription Packages'

    def __str__(self):
        return f'{self.name} (${self.monthly_price}/mo)'

    @property
    def yearly_savings(self):
        """Monthly equivalent of yearly price."""
        if self.yearly_price and self.monthly_price:
            annual_if_monthly = self.monthly_price * 12
            return annual_if_monthly - self.yearly_price
        return Decimal('0.00')


class Subscription(models.Model):
    """
    Active subscription for a Tenant.
    One tenant has one active subscription at a time.
    """

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'
        TRIAL = 'trial', 'Trial'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRIAL = 'trial', 'Trial'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'
        PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
        SUSPENDED = 'suspended', 'Suspended'

    # ── Relations ──────────────────────────────────────────────────────────────
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='subscriptions')
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.PROTECT, related_name='subscriptions')

    # ── Billing ────────────────────────────────────────────────────────────────
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # ── Dates ──────────────────────────────────────────────────────────────────
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    trial_ends_at = models.DateTimeField(blank=True, null=True)

    # ── Status ─────────────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    auto_renew = models.BooleanField(default=True)

    # ── Notifications Sent ─────────────────────────────────────────────────────
    expiry_7day_notified = models.BooleanField(default=False)
    expiry_3day_notified = models.BooleanField(default=False)
    expiry_1day_notified = models.BooleanField(default=False)
    expired_notified = models.BooleanField(default=False)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'

    def __str__(self):
        return f'{self.tenant.agency_name} – {self.package.name} ({self.status})'

    def check_and_update_status(self):
        """
        Automatically update subscription status to EXPIRED if end_date has passed.
        """
        if self.status in (self.Status.ACTIVE, self.Status.TRIAL) and self.end_date <= timezone.now():
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status'])
        return self.status

    @property
    def is_active(self):
        if self.status in (self.Status.ACTIVE, self.Status.TRIAL) and self.end_date <= timezone.now():
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status'])
            return False
        return self.status in (self.Status.ACTIVE, self.Status.TRIAL)

    @property
    def days_remaining(self):
        delta = self.end_date - timezone.now()
        return max(0, delta.days)

    def activate(self):
        self.status = self.Status.ACTIVE
        self.save(update_fields=['status'])

    def expire(self):
        self.status = self.Status.EXPIRED
        self.save(update_fields=['status'])


class SaaSPayment(models.Model):
    """
    Records subscription payments from tenants.
    Stored in the MAIN database.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='saas_payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, related_name='payments')
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.SET_NULL, null=True)

    transaction_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='USD')
    payment_method = models.CharField(max_length=50, blank=True)
    billing_cycle = models.CharField(max_length=10, choices=Subscription.BillingCycle.choices)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    gateway_response = models.JSONField(default=dict, blank=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SaaS Payment'

    def __str__(self):
        return f'{self.tenant.agency_name} – ${self.amount} ({self.status})'

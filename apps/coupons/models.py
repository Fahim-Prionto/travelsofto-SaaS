"""
apps/coupons/models.py

Coupon models for TENANT databases.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    """Discount coupon usable by customers."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage (%)'
        FIXED = 'fixed', 'Fixed Amount'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)

    discount_type = models.CharField(max_length=15, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.discount_value}{"%" if self.discount_type == "percentage" else " USD"})'

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active
            and self.start_date <= now <= self.end_date
            and self.used_count < self.usage_limit
        )

    def calculate_discount(self, order_amount: Decimal) -> Decimal:
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = order_amount * (self.discount_value / 100)
            if self.maximum_discount:
                discount = min(discount, self.maximum_discount)
        else:
            discount = self.discount_value
        return min(discount, order_amount)


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    customer_email = models.EmailField()
    order_reference = models.CharField(max_length=50)
    discount_given = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.coupon.code} used by {self.customer_email}'

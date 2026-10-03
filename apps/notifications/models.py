"""
apps/notifications/models.py

Notification models for TENANT databases.
"""
import uuid
from django.db import models


class Notification(models.Model):
    """In-app notification for users/admins."""

    class NotificationType(models.TextChoices):
        BOOKING = 'booking', 'Booking'
        VISA = 'visa', 'Visa Application'
        PAYMENT = 'payment', 'Payment'
        SUBSCRIPTION = 'subscription', 'Subscription'
        SUPPORT = 'support', 'Support Ticket'
        SYSTEM = 'system', 'System'
        GENERAL = 'general', 'General'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    recipient_email = models.EmailField(db_index=True)
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.GENERAL)
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient_email}: {self.title}'

    def mark_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])

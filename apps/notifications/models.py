"""
apps/notifications/models.py

Centralized Notification models for SaaS Agency & Platform notifications.
Stored in the MAIN database.
"""
import uuid
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    In-app & system notifications for Agencies and Admins.
    Handles:
      - Subscription alerts (expiring soon, renewal, status changes)
      - Payment approval / rejection confirmations
      - Super Admin announcements: Maintenance, Server Updates, Work/Part Updates, General
    """

    class NotificationType(models.TextChoices):
        SUBSCRIPTION = 'subscription', 'Subscription'
        PAYMENT = 'payment', 'Payment & Billing'
        MAINTENANCE = 'maintenance', 'System Maintenance'
        SERVER_UPDATE = 'server_update', 'Server & Infra Update'
        WORK_UPDATE = 'work_update', 'Work & Feature Update'
        SUPPORT = 'support', 'Support Ticket'
        SYSTEM = 'system', 'System Announcement'
        GENERAL = 'general', 'General'
        BOOKING = 'booking', 'Booking'
        VISA = 'visa', 'Visa Application'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='agency_notifications',
        help_text='Null if general platform announcement or targeted via recipient_email'
    )
    recipient_email = models.EmailField(blank=True, default='', db_index=True)
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        db_index=True
    )
    priority = models.CharField(
        max_length=15,
        choices=Priority.choices,
        default=Priority.NORMAL
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(max_length=500, blank=True, default='')
    is_broadcast = models.BooleanField(default=False, help_text='Sent to all agencies')
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_read']),
            models.Index(fields=['recipient_email', 'is_read']),
        ]

    def __str__(self):
        target = self.tenant.agency_name if self.tenant else (self.recipient_email or 'All Agencies')
        return f'[{self.notification_type}] {target}: {self.title}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @property
    def badge_info(self):
        """Helper to get visual badges and icons for UI rendering."""
        mapping = {
            self.NotificationType.SUBSCRIPTION: {
                'icon': 'fa-solid fa-arrows-rotate',
                'bg': 'bg-primary-subtle',
                'text': 'text-primary',
                'border': 'border-primary-subtle',
                'label': 'Subscription',
            },
            self.NotificationType.PAYMENT: {
                'icon': 'fa-solid fa-credit-card',
                'bg': 'bg-success-subtle',
                'text': 'text-success',
                'border': 'border-success-subtle',
                'label': 'Payment',
            },
            self.NotificationType.MAINTENANCE: {
                'icon': 'fa-solid fa-screwdriver-wrench',
                'bg': 'bg-warning-subtle',
                'text': 'text-warning-emphasis',
                'border': 'border-warning-subtle',
                'label': 'Maintenance',
            },
            self.NotificationType.SERVER_UPDATE: {
                'icon': 'fa-solid fa-server',
                'bg': 'bg-info-subtle',
                'text': 'text-info-emphasis',
                'border': 'border-info-subtle',
                'label': 'Server Update',
            },
            self.NotificationType.WORK_UPDATE: {
                'icon': 'fa-solid fa-rocket',
                'bg': 'bg-purple-subtle',
                'text': 'text-purple',
                'border': 'border-purple-subtle',
                'label': 'Feature Update',
            },
            self.NotificationType.SUPPORT: {
                'icon': 'fa-solid fa-headset',
                'bg': 'bg-secondary-subtle',
                'text': 'text-secondary',
                'border': 'border-secondary-subtle',
                'label': 'Support',
            },
            self.NotificationType.SYSTEM: {
                'icon': 'fa-solid fa-bullhorn',
                'bg': 'bg-danger-subtle',
                'text': 'text-danger',
                'border': 'border-danger-subtle',
                'label': 'System Alert',
            },
        }
        return mapping.get(self.notification_type, {
            'icon': 'fa-solid fa-bell',
            'bg': 'bg-light',
            'text': 'text-dark',
            'border': 'border-secondary-subtle',
            'label': 'General',
        })

"""
apps/support/models.py

Platform & Tenant Support Ticket models for Live Chat & Ticket System.
Stores Agency-to-Platform Support tickets in the MAIN database.
"""
import uuid
import random, string
from django.db import models
from django.conf import settings


class AgencySupportTicket(models.Model):
    """
    Live Support Chat tickets raised by Agency Tenants to Super Admin & Support Team.
    Stored in the MAIN database.
    """

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        REPLIED = 'replied', 'Replied'
        IN_PROGRESS = 'in_progress', 'In Progress'
        CLOSED = 'closed', 'Closed'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ticket_code = models.CharField(max_length=20, unique=True)

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='support_tickets')
    assigned_supporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_agency_tickets'
    )

    subject = models.CharField(max_length=500)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.ticket_code} – {self.tenant.agency_name}: {self.subject}'

    def save(self, *args, **kwargs):
        if not self.ticket_code:
            self.ticket_code = 'SUP' + ''.join(random.choices(string.digits, k=7))
        super().save(*args, **kwargs)


class AgencySupportMessage(models.Model):
    """Live Chat messages within an Agency Support ticket."""

    class SenderType(models.TextChoices):
        AGENCY = 'agency', 'Agency'
        SUPER_ADMIN = 'super_admin', 'Super Admin / Supporter'

    ticket = models.ForeignKey(AgencySupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sender_type = models.CharField(max_length=15, choices=SenderType.choices)
    sender_name = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.sender_type}] {self.ticket.ticket_code}'


# Kept for compatibility with tenant customer tickets
class SupportTicket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        REPLIED = 'replied', 'Replied'
        IN_PROGRESS = 'in_progress', 'In Progress'
        CLOSED = 'closed', 'Closed'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ticket_code = models.CharField(max_length=20, unique=True)
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255)
    subject = models.CharField(max_length=500)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.ticket_code} – {self.subject}'

    def save(self, *args, **kwargs):
        if not self.ticket_code:
            self.ticket_code = 'TKT' + ''.join(random.choices(string.digits, k=7))
        super().save(*args, **kwargs)


class SupportMessage(models.Model):
    class SenderType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SenderType.choices)
    sender_name = models.CharField(max_length=255)
    message = models.TextField()
    attachment = models.FileField(upload_to='support/attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

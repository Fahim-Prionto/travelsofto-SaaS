"""
apps/visa/models.py

Visa Service and Visa Application models for TENANT databases.
"""
import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField


class VisaService(models.Model):
    """A visa service offered by the travel agency."""

    class VisaType(models.TextChoices):
        TOURIST = 'tourist', 'Tourist Visa'
        BUSINESS = 'business', 'Business Visa'
        STUDENT = 'student', 'Student Visa'
        WORK = 'work', 'Work Visa'
        TRANSIT = 'transit', 'Transit Visa'
        FAMILY = 'family', 'Family Visa'
        OTHER = 'other', 'Other'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    visa_type = models.CharField(max_length=20, choices=VisaType.choices)
    country = models.ForeignKey(
        'destinations.Country',
        on_delete=models.SET_NULL,
        null=True,
        related_name='visa_services',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    processing_time = models.CharField(max_length=100, help_text='e.g. 5-7 business days')
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True, help_text='List of required documents')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    featured_image = models.ImageField(upload_to='visa/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Visa Service'

    def __str__(self):
        return f'{self.name} ({self.get_visa_type_display()})'


class VisaApplication(models.Model):
    """Customer visa application submitted via the tenant website."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    application_code = models.CharField(max_length=20, unique=True)

    # ── Relations ──────────────────────────────────────────────────────────────
    visa_service = models.ForeignKey(VisaService, on_delete=models.PROTECT, related_name='applications')
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255)
    customer_mobile = models.CharField(max_length=20, blank=True)

    # ── Application Info ───────────────────────────────────────────────────────
    passport_number = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    intended_travel_date = models.DateField(blank=True, null=True)
    duration_of_stay = models.PositiveIntegerField(default=30, help_text='Days')
    purpose_of_visit = models.TextField(blank=True)

    # ── Payment ────────────────────────────────────────────────────────────────
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=20,
        choices=[('pending','Pending'),('paid','Paid'),('failed','Failed'),('refunded','Refunded')],
        default='pending',
    )

    # ── Status ─────────────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # ── Tracking ───────────────────────────────────────────────────────────────
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Visa Application'

    def __str__(self):
        return f'{self.application_code} – {self.customer_name}'

    def save(self, *args, **kwargs):
        if not self.application_code:
            import random, string
            self.application_code = 'VIS' + ''.join(random.choices(string.digits, k=7))
        super().save(*args, **kwargs)


class VisaDocument(models.Model):
    """Documents uploaded for a visa application."""

    class DocumentType(models.TextChoices):
        PASSPORT = 'passport', 'Passport Copy'
        PHOTO = 'photo', 'Passport Photo'
        BANK_STATEMENT = 'bank_statement', 'Bank Statement'
        INVITATION = 'invitation', 'Invitation Letter'
        HOTEL_BOOKING = 'hotel_booking', 'Hotel Booking'
        FLIGHT_TICKET = 'flight_ticket', 'Flight Ticket'
        OTHER = 'other', 'Other Document'

    application = models.ForeignKey(VisaApplication, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to='visa/documents/')
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_document_type_display()} for {self.application.application_code}'

"""
apps/kyc/models.py

KYC (Know Your Customer) models for TENANT databases.
"""
import uuid
from django.db import models


class KYCRequest(models.Model):
    """KYC verification request submitted by a customer."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class DocumentType(models.TextChoices):
        PASSPORT = 'passport', 'Passport'
        NATIONAL_ID = 'national_id', 'National ID'
        DRIVING_LICENSE = 'driving_license', 'Driving License'
        BIRTH_CERTIFICATE = 'birth_certificate', 'Birth Certificate'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer_email = models.EmailField(db_index=True)
    customer_name = models.CharField(max_length=255)

    document_type = models.CharField(max_length=25, choices=DocumentType.choices)
    document_number = models.CharField(max_length=100)
    document_front = models.ImageField(upload_to='kyc/documents/')
    document_back = models.ImageField(upload_to='kyc/documents/', blank=True, null=True)
    selfie = models.ImageField(upload_to='kyc/selfies/', blank=True, null=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'KYC: {self.customer_email} – {self.status}'

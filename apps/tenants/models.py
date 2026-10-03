"""
apps/tenants/models.py

Core multi-tenant models for ViserTrip.
Every travel agency (tenant) is represented here in the MAIN database.
Each tenant gets a separate PostgreSQL database identified by db_name.
"""
import uuid
import re
from django.db import models
from django.utils import timezone
from django.conf import settings
from .agency_models import *


def generate_slug(agency_name: str) -> str:
    """Convert agency name to a URL-safe slug."""
    slug = agency_name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:50]


class Tenant(models.Model):
    """
    Represents a travel agency that has subscribed to ViserTrip SaaS.
    Stored in the MAIN database.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        SUSPENDED = 'suspended', 'Suspended'
        TRIAL = 'trial', 'Trial'
        EXPIRED = 'expired', 'Expired'
        PENDING = 'pending', 'Pending'

    # ── Identifiers ────────────────────────────────────────────────────────────
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    db_name = models.CharField(
        max_length=100,
        unique=True,
        help_text='PostgreSQL database name for this tenant (e.g., tenant_abc_travel)',
    )

    # ── Agency Information ─────────────────────────────────────────────────────
    agency_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    favicon = models.ImageField(upload_to='tenant_favicons/', blank=True, null=True)

    # ── Admin Account ──────────────────────────────────────────────────────────
    # FK to the main User model (tenant admin user)
    admin_user = models.OneToOneField(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_tenant',
    )

    # ── Status ─────────────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # ── Database Status ────────────────────────────────────────────────────────
    db_created = models.BooleanField(default=False)
    db_migrated = models.BooleanField(default=False)

    # ── Provisioning ───────────────────────────────────────────────────────────
    provisioning_started_at = models.DateTimeField(blank=True, null=True)
    provisioning_completed_at = models.DateTimeField(blank=True, null=True)
    provisioning_error = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'

    def __str__(self):
        return f'{self.agency_name} ({self.slug})'

    @property
    def subdomain_url(self):
        return f'http://{self.slug}.{settings.BASE_DOMAIN}'

    @property
    def admin_url(self):
        return f'{self.subdomain_url}/admin-panel/'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def get_db_config(self):
        """Return the database configuration dict for this tenant."""
        main_db = settings.DATABASES['default']
        config = {
            'ENGINE': main_db['ENGINE'],
            'NAME': self.db_name,
            'USER': main_db['USER'],
            'PASSWORD': main_db['PASSWORD'],
            'HOST': main_db['HOST'],
            'PORT': main_db['PORT'],
            'ATOMIC_REQUESTS': main_db.get('ATOMIC_REQUESTS', False),
            'AUTOCOMMIT': main_db.get('AUTOCOMMIT', True),
            'TIME_ZONE': main_db.get('TIME_ZONE', None),
            'CONN_MAX_AGE': main_db.get('CONN_MAX_AGE', 0),
            'CONN_HEALTH_CHECKS': main_db.get('CONN_HEALTH_CHECKS', False),
            'OPTIONS': main_db.get('OPTIONS', {}),
            'TIME_ZONE': settings.TIME_ZONE,
        }
        return config

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = generate_slug(self.agency_name)
            slug = base_slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug

        if not self.db_name:
            safe = re.sub(r'[^a-z0-9_]', '_', self.slug.replace('-', '_'))
            base_db = f'tenant_{safe}'
            db_name = base_db
            counter = 1
            while Tenant.objects.filter(db_name=db_name).exclude(pk=self.pk).exists():
                db_name = f'{base_db}_{counter}'
                counter += 1
            self.db_name = db_name

        super().save(*args, **kwargs)


class TenantDomain(models.Model):
    """
    Domains associated with a tenant.
    A tenant may have a subdomain + an optional custom domain.
    """

    class DomainType(models.TextChoices):
        SUBDOMAIN = 'subdomain', 'Subdomain'
        CUSTOM = 'custom', 'Custom Domain'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PENDING = 'pending', 'Pending Verification'
        FAILED = 'failed', 'Verification Failed'
        INACTIVE = 'inactive', 'Inactive'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    domain_type = models.CharField(max_length=20, choices=DomainType.choices, default=DomainType.SUBDOMAIN)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    ssl_enabled = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return f'{self.domain} → {self.tenant.agency_name}'


class TenantProvisioningLog(models.Model):
    """Logs every step of tenant database provisioning."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Success'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='provisioning_logs')
    step = models.CharField(max_length=100)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.level.upper()}] {self.tenant.slug}: {self.step}'


class GlobalSetting(models.Model):
    """Key-value store for platform-wide settings."""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

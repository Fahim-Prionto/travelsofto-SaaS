"""
apps/travel_packages/models.py

Travel Package models for TENANT databases.
Each tenant has its own isolated set of travel packages.
"""
import uuid
from django.db import models
from django.utils import timezone


class TravelPackage(models.Model):
    """A travel package offered by the tenant agency."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        DRAFT = 'draft', 'Draft'
        SOLD_OUT = 'sold_out', 'Sold Out'

    class DifficultyLevel(models.TextChoices):
        EASY = 'easy', 'Easy'
        MODERATE = 'moderate', 'Moderate'
        CHALLENGING = 'challenging', 'Challenging'

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # ── Basic Info ─────────────────────────────────────────────────────────────
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)

    # ── Destination ────────────────────────────────────────────────────────────
    destination = models.ForeignKey(
        'destinations.Destination',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='packages',
    )
    destination_name = models.CharField(max_length=255, blank=True)  # fallback

    # ── Schedule ───────────────────────────────────────────────────────────────
    travel_date = models.DateField(blank=True, null=True)
    return_date = models.DateField(blank=True, null=True)
    duration_days = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(max_length=15, choices=DifficultyLevel.choices, default=DifficultyLevel.EASY)

    # ── Pricing ────────────────────────────────────────────────────────────────
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=5, default='USD')

    # ── Capacity ───────────────────────────────────────────────────────────────
    total_seats = models.PositiveIntegerField(default=20)
    available_seats = models.PositiveIntegerField(default=20)


    connected_bus_schedule = models.ForeignKey(
        'bus.BusSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='connected_packages',
    )

    # ── Media ──────────────────────────────────────────────────────────────────
    featured_image = models.ImageField(upload_to='packages/', blank=True, null=True)

    # ── Services ───────────────────────────────────────────────────────────────
    included_services = models.JSONField(default=list, blank=True)
    excluded_services = models.JSONField(default=list, blank=True)

    # ── Meta ───────────────────────────────────────────────────────────────────
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    # ── Stats ──────────────────────────────────────────────────────────────────
    view_count = models.PositiveIntegerField(default=0)
    booking_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Travel Package'
        verbose_name_plural = 'Travel Packages'

    def __str__(self):
        return self.name

    @property
    def effective_price(self):
        return self.discounted_price if self.discounted_price else self.price

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.available_seats > 0


class PackageImage(models.Model):
    """Multiple images for a travel package."""

    package = models.ForeignKey(TravelPackage, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='packages/gallery/')
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f'Image for {self.package.name}'

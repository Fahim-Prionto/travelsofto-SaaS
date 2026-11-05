"""
apps/destinations/models.py

Destination models (Country, City, Destination) for TENANT databases.
"""
from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True, blank=True)
    flag = models.ImageField(upload_to='flags/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'countries'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            import string, random
            db = kwargs.get('using') or getattr(getattr(self, '_state', None), 'db', None) or 'default'
            clean = ''.join(c for c in (self.name or '').upper() if c.isalnum())
            base = clean[:3] if len(clean) >= 3 else clean.ljust(3, 'X')
            code_candidate = base
            qs = Country.objects.using(db)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            attempts = 0
            while qs.filter(code=code_candidate).exists() and attempts < 100:
                code_candidate = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
                attempts += 1
            self.code = code_candidate
        else:
            self.code = self.code.strip().upper()[:3]
        super().save(*args, **kwargs)


class City(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'cities'
        unique_together = [['name', 'country']]

    def __str__(self):
        return f'{self.name}, {self.country.name}'


class Destination(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, related_name='destinations')
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='destinations')

    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    featured_image = models.ImageField(upload_to='destinations/', blank=True, null=True)

    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            import string, random
            db = kwargs.get('using') or getattr(getattr(self, '_state', None), 'db', None) or 'default'
            clean = ''.join(c for c in (self.name or '').upper() if c.isalnum())
            base = clean[:3] if len(clean) >= 3 else clean.ljust(3, 'X')
            code_candidate = base
            qs = Country.objects.using(db)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            attempts = 0
            while qs.filter(code=code_candidate).exists() and attempts < 100:
                code_candidate = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
                attempts += 1
            self.code = code_candidate
        else:
            self.code = self.code.strip().upper()[:3]
        super().save(*args, **kwargs)


class DestinationImage(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='destinations/gallery/')
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

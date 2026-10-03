"""
apps/travel_packages/serializers.py
"""
from rest_framework import serializers
from apps.travel_packages.models import TravelPackage, PackageImage


class TravelPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelPackage
        fields = [
            'uid', 'name', 'slug', 'description', 'short_description',
            'price', 'discounted_price', 'duration_days', 'difficulty',
            'total_seats', 'available_seats', 'status', 'is_featured'
        ]

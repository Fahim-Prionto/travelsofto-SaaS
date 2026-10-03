"""
apps/visa/serializers.py
"""
from rest_framework import serializers
from apps.visa.models import VisaService, VisaApplication


class VisaServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaService
        fields = ['uid', 'name', 'visa_type', 'price', 'processing_time', 'description', 'requirements', 'is_active']


class VisaApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaApplication
        fields = [
            'application_code', 'customer_name', 'customer_email', 'customer_mobile',
            'passport_number', 'nationality', 'date_of_birth', 'status', 'submitted_at'
        ]
        read_only_fields = ['application_code', 'status', 'submitted_at']

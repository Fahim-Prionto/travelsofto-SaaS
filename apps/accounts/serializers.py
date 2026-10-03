"""
apps/accounts/serializers.py

Django REST Framework Serializers for Account & Auth APIs.
"""
from rest_framework import serializers
from apps.accounts.models import User, UserProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'uid', 'email', 'first_name', 'last_name', 'mobile',
            'role', 'tenant_id', 'is_active', 'email_verified',
            'mobile_verified', 'balance', 'date_joined'
        ]
        read_only_fields = ['uid', 'role', 'tenant_id', 'balance', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'mobile']

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            mobile=validated_data.get('mobile', ''),
            role=User.Role.CUSTOMER,
        )
        return user

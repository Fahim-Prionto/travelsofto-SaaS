"""
apps/accounts/api_views.py

API Views for Customer Registration & User Profile retrieval.
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer, RegisterSerializer


class CustomerRegisterAPIView(generics.CreateAPIView):
    """API endpoint for customer self-registration."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileAPIView(generics.RetrieveUpdateAPIView):
    """API endpoint for current user profile."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

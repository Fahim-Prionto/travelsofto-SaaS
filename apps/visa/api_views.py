"""
apps/visa/api_views.py
"""
from rest_framework import generics, permissions
from apps.visa.models import VisaService, VisaApplication
from apps.visa.serializers import VisaServiceSerializer, VisaApplicationSerializer


class VisaServiceListAPIView(generics.ListAPIView):
    """API list endpoint for active visa services."""
    serializer_class = VisaServiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        db = f'tenant_{self.request.tenant.slug}' if getattr(self.request, 'tenant', None) else 'default'
        try:
            qs = VisaService.objects.using(db).filter(is_active=True)
            list(qs[:1])
            return qs
        except Exception:
            return VisaService.objects.none()


class VisaApplicationCreateAPIView(generics.CreateAPIView):
    """API endpoint for customer visa application submission."""
    serializer_class = VisaApplicationSerializer
    permission_classes = [permissions.AllowAny]

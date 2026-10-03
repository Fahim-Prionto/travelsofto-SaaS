"""
apps/travel_packages/api_views.py
"""
from rest_framework import generics, permissions
from apps.travel_packages.models import TravelPackage
from apps.travel_packages.serializers import TravelPackageSerializer


class TravelPackageListAPIView(generics.ListAPIView):
    """API endpoint to list active travel packages for tenant."""
    serializer_class = TravelPackageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        db = f'tenant_{self.request.tenant.slug}' if getattr(self.request, 'tenant', None) else 'default'
        try:
            # Force evaluation to prevent unmigrated table crashes
            qs = TravelPackage.objects.using(db).filter(status='active')
            list(qs[:1])
            return qs
        except Exception:
            return TravelPackage.objects.none()


class TravelPackageDetailAPIView(generics.RetrieveAPIView):
    """API endpoint to retrieve single travel package detail."""
    serializer_class = TravelPackageSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        db = f'tenant_{self.request.tenant.slug}' if getattr(self.request, 'tenant', None) else 'default'
        try:
            return TravelPackage.objects.using(db).filter(status='active')
        except Exception:
            return TravelPackage.objects.none()

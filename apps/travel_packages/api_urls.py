from django.urls import path
from . import api_views

app_name = 'travel_packages_api'

urlpatterns = [
    path('', api_views.TravelPackageListAPIView.as_view(), name='api_package_list'),
    path('<slug:slug>/', api_views.TravelPackageDetailAPIView.as_view(), name='api_package_detail'),
]

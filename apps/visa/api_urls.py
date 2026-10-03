from django.urls import path
from . import api_views

app_name = 'visa_api'

urlpatterns = [
    path('services/', api_views.VisaServiceListAPIView.as_view(), name='api_visa_services'),
    path('apply/', api_views.VisaApplicationCreateAPIView.as_view(), name='api_visa_apply'),
]

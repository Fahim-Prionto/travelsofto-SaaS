from django.urls import path
from . import api_views

app_name = 'accounts_api'

urlpatterns = [
    path('register/', api_views.CustomerRegisterAPIView.as_view(), name='api_register'),
    path('me/', api_views.UserProfileAPIView.as_view(), name='api_profile'),
]

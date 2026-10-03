from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('register-agency/', views.agency_register, name='agency_register'),
    path('register/', views.customer_register, name='customer_register'),
    path('logout/', views.user_logout, name='logout'),
]

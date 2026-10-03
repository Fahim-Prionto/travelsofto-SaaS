from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tenants/', views.tenant_list, name='tenant_list'),
    path('tenants/create/', views.tenant_create, name='tenant_create'),
    path('tenants/<slug:slug>/', views.tenant_detail, name='tenant_detail'),
    path('tenants/<slug:slug>/delete/', views.tenant_delete, name='tenant_delete'),
    path('tenants/<slug:slug>/support-login/', views.tenant_support_login, name='tenant_support_login'),
    path('packages/', views.package_list, name='package_list'),
    path('packages/<int:pk>/edit/', views.package_edit, name='package_edit'),
    path('analytics/', views.analytics, name='analytics'),
    path('domains/', views.domain_management, name='domain_management'),
    path('payments/', views.saas_payments, name='saas_payments'),
    path('payments/<int:payment_id>/approve/', views.approve_saas_payment, name='approve_saas_payment'),
    path('payments/<int:payment_id>/reject/', views.reject_saas_payment, name='reject_saas_payment'),
    path('support/', views.support_tickets, name='support_tickets'),
    path('support/chat/<int:ticket_id>/', views.support_chat, name='support_chat'),
    path('support/members/', views.support_members, name='support_members'),
    path('profile/', views.profile, name='profile'),
    path('global-settings/', views.global_settings, name='global_settings'),
]

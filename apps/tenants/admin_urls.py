from django.urls import path
from . import admin_views, agency_views

app_name = 'admin_panel'

urlpatterns = [
    # Dashboard
    path('', admin_views.dashboard, name='dashboard'),

    # Agency Candidate Management
    path('candidates/', agency_views.candidate_list, name='candidate_list'),
    path('candidates/create/', agency_views.candidate_create, name='candidate_create'),
    path('candidates/<int:pk>/edit/', agency_views.candidate_edit, name='candidate_edit'),
    path('candidates/<int:pk>/delete/', agency_views.candidate_delete, name='candidate_delete'),
    path('candidates/<int:pk>/add-payment/', agency_views.candidate_add_payment, name='candidate_add_payment'),
    path('candidates/<int:pk>/upload-document/', agency_views.candidate_upload_document, name='candidate_upload_document'),
    path('candidates/documents/<int:doc_pk>/delete/', agency_views.candidate_delete_document, name='candidate_delete_document'),
    path('candidates/id-card-print/', agency_views.candidate_id_card_bulk, name='candidate_id_card_bulk'),
    path('candidates/<int:pk>/update-stage/', agency_views.candidate_update_stage, name='candidate_update_stage'),
    path('candidates/<int:pk>/download/', agency_views.candidate_download, name='candidate_download'),
    path('candidates/<int:pk>/invoice/', agency_views.candidate_invoice, name='candidate_invoice'),

    # Connected Stage Management Pages
    path('stages/<str:stage_name>/', agency_views.stage_view, name='stage_view'),

    # Okala & Visa Lot
    path('okala-management/', agency_views.okala_list, name='okala_list'),

    # Financial Requisitions & Accounts
    path('requisitions/', agency_views.requisitions_list, name='requisitions_list'),
    path('accounts-vouchers/', agency_views.accounts_vouchers, name='accounts_vouchers'),

    # HR & Daily Movement / Leave
    path('hr-movement-leave/', agency_views.hr_movement_leave, name='hr_movement_leave'),
    path('office-expenses/', agency_views.office_expense_list, name='office_expense_list'),

    # Reports Engine
    path('agency-reports/', agency_views.reports_hub, name='reports_hub'),

    # Master Agency Settings
    path('master-settings/', agency_views.master_settings, name='master_settings'),

    # Core Travel Packages & Visa Services
    path('packages/', admin_views.package_list, name='package_list'),
    path('packages/create/', admin_views.package_create, name='package_create'),
    path('packages/<int:pk>/edit/', admin_views.package_edit, name='package_edit'),
    path('packages/<int:pk>/delete/', admin_views.package_delete, name='package_delete'),
    path('packages/gallery-image/<int:pk>/delete/', admin_views.package_gallery_image_delete, name='package_gallery_image_delete'),

    path('visa-services/', admin_views.visa_service_list, name='visa_service_list'),
    path('visa-services/create/', admin_views.visa_service_create, name='visa_service_create'),

    path('bookings/', admin_views.booking_list, name='booking_list'),
    path('bookings/create/', admin_views.booking_create, name='booking_create'),
    path('bookings/<int:pk>/edit/', admin_views.booking_edit, name='booking_edit'),
    path('bookings/<int:pk>/delete/', admin_views.booking_delete, name='booking_delete'),
    path('bookings/<int:pk>/invoice/', admin_views.booking_invoice, name='booking_invoice'),
    path('bookings/<int:pk>/status/<str:status>/', admin_views.booking_update_status, name='booking_update_status'),
    path('bookings/<int:pk>/payment-status/<str:payment_status>/', admin_views.booking_update_payment_status, name='booking_update_payment_status'),

    path('visa-applications/', admin_views.visa_app_list, name='visa_app_list'),
    path('visa-applications/<int:pk>/status/<str:status>/', admin_views.visa_app_update_status, name='visa_app_update_status'),

    path('customers/', admin_views.customer_list, name='customer_list'),
    path('customers/create/', admin_views.customer_create, name='customer_create'),
    path('customers/<int:pk>/toggle-ban/', admin_views.customer_toggle_ban, name='customer_toggle_ban'),

    path('staff/', admin_views.staff_list, name='staff_list'),
    path('staff/create/', admin_views.staff_create, name='staff_create'),
    path('staff/<int:pk>/toggle-ban/', admin_views.staff_toggle_ban, name='staff_toggle_ban'),
    path('staff/<int:pk>/delete/', admin_views.staff_delete, name='staff_delete'),

    # Ambassadors
    path('ambassadors/', admin_views.ambassador_list, name='ambassador_list'),
    path('ambassadors/create/', admin_views.ambassador_create, name='ambassador_create'),
    path('ambassadors/<int:pk>/toggle-ban/', admin_views.ambassador_toggle_ban, name='ambassador_toggle_ban'),
    path('ambassadors/<int:pk>/delete/', admin_views.ambassador_delete, name='ambassador_delete'),

    # Bus Ticket System
    path('bus/operators/', admin_views.bus_operator_list, name='bus_operator_list'),
    path('bus/operators/create/', admin_views.bus_operator_create, name='bus_operator_create'),
    path('bus/operators/<int:pk>/delete/', admin_views.bus_operator_delete, name='bus_operator_delete'),
    path('bus/routes/', admin_views.bus_route_list, name='bus_route_list'),
    path('bus/routes/<int:pk>/delete/', admin_views.bus_route_delete, name='bus_route_delete'),
    path('bus/schedules/', admin_views.bus_schedule_list, name='bus_schedule_list'),
    path('bus/schedules/<int:pk>/delete/', admin_views.bus_schedule_delete, name='bus_schedule_delete'),
    path('bus/bookings/', admin_views.bus_booking_list, name='bus_booking_list'),
    path('bus/bookings/<int:pk>/status/<str:status>/', admin_views.bus_booking_update_status, name='bus_booking_update_status'),

    # Air Ticket System
    path('air/airlines/', admin_views.airline_list, name='airline_list'),
    path('air/airlines/create/', admin_views.airline_create, name='airline_create'),
    path('air/airlines/<int:pk>/delete/', admin_views.airline_delete, name='airline_delete'),
    path('air/routes/', admin_views.flight_route_list, name='flight_route_list'),
    path('air/routes/<int:pk>/delete/', admin_views.flight_route_delete, name='flight_route_delete'),
    path('air/schedules/', admin_views.flight_schedule_list, name='flight_schedule_list'),
    path('air/schedules/<int:pk>/delete/', admin_views.flight_schedule_delete, name='flight_schedule_delete'),
    path('air/bookings/', admin_views.air_booking_list, name='air_booking_list'),
    path('air/bookings/<int:pk>/status/<str:status>/', admin_views.air_booking_update_status, name='air_booking_update_status'),

    path('cms-settings/', admin_views.cms_settings, name='cms_settings'),
    path('domains/', admin_views.domain_settings, name='domain_settings'),

    path('subscription/', admin_views.my_subscription, name='my_subscription'),
    path('subscription/checkout/', admin_views.subscription_checkout, name='subscription_checkout'),
    path('subscription/pending/', admin_views.subscription_pending, name='subscription_pending'),

    path('support/', admin_views.agency_support, name='agency_support'),
]

"""
apps/tenants/customer_views.py

Customer Dashboard & Portal Views (Level 3).
Provides interface for registered customers of a travel agency to:
  - View personal trip dashboard (total bookings, completed trips, pending applications, spending)
  - View booking history with status badges & details
  - View visa application history & tracking
  - View payment transaction history
  - Manage user profile settings
  - Manage support tickets
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum

from apps.bookings.models import Booking
from apps.visa.models import VisaApplication
from apps.bus.models import BusBooking
from apps.bookings.air_models import AirTicketBooking
from apps.payments.models import Payment
from apps.support.models import SupportTicket, SupportMessage


from django.conf import settings

def get_tenant_db(request):
    """Return database alias for current tenant, dynamically registering DB config if missing."""
    from apps.tenants.models import Tenant
    tenant_slug = None
    if hasattr(request, 'user') and getattr(request.user, 'tenant_id', None):
        tenant_slug = request.user.tenant_id
    elif getattr(request, 'tenant', None):
        tenant_slug = request.tenant.slug

    if tenant_slug:
        db_alias = f'tenant_{tenant_slug}'
        if db_alias not in settings.DATABASES:
            try:
                tenant_obj = getattr(request, 'tenant', None)
                if not tenant_obj:
                    tenant_obj = Tenant.objects.filter(slug=tenant_slug).first()
                if tenant_obj:
                    settings.DATABASES[db_alias] = tenant_obj.get_db_config()
            except Exception:
                return 'default'

        if db_alias in settings.DATABASES:
            from apps.tenants.routers import set_tenant_db
            set_tenant_db(db_alias)
            return db_alias

    return 'default'


@login_required
def customer_dashboard(request):
    """Customer Portal Dashboard."""
    db = get_tenant_db(request)
    email = request.user.email

    try:
        total_bookings = Booking.objects.using(db).filter(customer_email=email).count()
        bus_bookings_count = BusBooking.objects.using(db).filter(customer_email=email).count()
        air_bookings_count = AirTicketBooking.objects.using(db).filter(customer_email=email).count()
        completed_trips = Booking.objects.using(db).filter(customer_email=email, status='completed').count()
        pending_bookings = Booking.objects.using(db).filter(customer_email=email, status='pending').count()
        visa_apps = VisaApplication.objects.using(db).filter(customer_email=email).count()
        total_spending = Payment.objects.using(db).filter(customer_email=email, status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        recent_bookings = Booking.objects.using(db).filter(customer_email=email).order_by('-booked_at')[:5]
    except Exception:
        total_bookings = bus_bookings_count = air_bookings_count = completed_trips = pending_bookings = visa_apps = 0
        total_spending = Decimal('0.00')
        recent_bookings = []

    context = {
        'total_bookings': total_bookings,
        'bus_bookings_count': bus_bookings_count,
        'air_bookings_count': air_bookings_count,
        'completed_trips': completed_trips,
        'pending_bookings': pending_bookings,
        'visa_apps': visa_apps,
        'total_spending': total_spending,
        'recent_bookings': recent_bookings,
    }
    return render(request, 'customer/dashboard.html', context)


@login_required
def customer_bookings(request):
    """Customer Booking History (Travel Packages)."""
    db = get_tenant_db(request)
    try:
        bookings = Booking.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        bookings = []
    return render(request, 'customer/bookings.html', {'bookings': bookings})


@login_required
def customer_bus_bookings(request):
    """Customer Bus Ticket Bookings History."""
    db = get_tenant_db(request)
    try:
        bookings = BusBooking.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        bookings = []
    return render(request, 'customer/bus_bookings.html', {'bookings': bookings})


@login_required
def customer_air_bookings(request):
    """Customer Air Ticket Bookings History."""
    db = get_tenant_db(request)
    try:
        bookings = AirTicketBooking.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        bookings = []
    return render(request, 'customer/air_bookings.html', {'bookings': bookings})


@login_required
def customer_visa_history(request):
    """Customer Visa Application History & Status Tracking."""
    db = get_tenant_db(request)
    try:
        applications = VisaApplication.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        applications = []
    return render(request, 'customer/visa_history.html', {'applications': applications})


@login_required
def customer_payments(request):
    """Customer Payment History."""
    db = get_tenant_db(request)
    try:
        payments = Payment.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        payments = []
    return render(request, 'customer/payments.html', {'payments': payments})


@login_required
def customer_support(request):
    """Customer Support Tickets."""
    db = get_tenant_db(request)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        priority = request.POST.get('priority', 'medium')

        ticket = SupportTicket.objects.using(db).create(
            customer_email=request.user.email,
            customer_name=request.user.full_name,
            subject=subject,
            priority=priority,
            status='open',
        )
        SupportMessage.objects.using(db).create(
            ticket=ticket,
            sender_type='customer',
            sender_name=request.user.full_name,
            message=message,
        )
        messages.success(request, f'Support ticket {ticket.ticket_code} created successfully!')
        return redirect('public:customer_support')

    try:
        tickets = SupportTicket.objects.using(db).filter(customer_email=request.user.email)
    except Exception:
        tickets = []

    return render(request, 'customer/support.html', {'tickets': tickets})


@login_required
def customer_profile(request):
    """Customer Profile & Security Settings."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        mobile = request.POST.get('mobile', '').strip()

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.mobile = mobile
        request.user.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('public:customer_profile')

    return render(request, 'customer/profile.html')

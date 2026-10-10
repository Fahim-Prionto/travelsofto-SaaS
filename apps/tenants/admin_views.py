"""
apps/tenants/admin_views.py

Full implementation of Agency Admin Panel (Level 2).
Provides CRUD management for:
  - Agency Dashboard & Analytics
  - Travel Packages (Add, Edit, Delete, Toggle Status)
  - Visa Services (Add, Edit, Delete, Toggle Status)
  - Bookings (List, Status Update, Details)
  - Visa Applications (List, Review, Status Update)
  - User & Customer Management (List, Ban/Activate, Balance Adjustment)
  - Website CMS Settings (Hero, About, Testimonials, FAQ)
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone

from apps.accounts.models import User
from apps.travel_packages.models import TravelPackage, PackageImage
from apps.visa.models import VisaService, VisaApplication, VisaDocument
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.destinations.models import Destination, Country
from apps.cms.models import HeroSection, WebsiteSetting, Testimonial, FAQ
from apps.tenants.agency_models import Candidate, CandidatePayment, VisaLot, OfficeExpense


from apps.tenants.models import Tenant, TenantDomain
from apps.subscriptions.models import Subscription, SaaSPayment, SubscriptionPackage
from django.conf import settings

def get_tenant_db(request):
    """Return database alias for current tenant, dynamically registering DB config if missing."""
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


def check_agency_subscription(request):
    """Helper to check if current agency has an active subscription or pending payment."""
    if request.user.is_super_admin or 'support_mode_tenant_id' in request.session:
        return True, None, None

    if not request.user.tenant_id:
        return True, None, None

    try:
        tenant = Tenant.objects.get(slug=request.user.tenant_id)
        sub = tenant.subscriptions.order_by('-created_at').first()
        
        # If subscription is pending payment or tenant inactive, block access
        if tenant.status in (Tenant.Status.PENDING, Tenant.Status.INACTIVE, Tenant.Status.SUSPENDED) or (sub and sub.status in ('pending_payment', 'expired', 'suspended')):
            pending_payment = SaaSPayment.objects.filter(tenant=tenant, status='pending').exists()
            if pending_payment:
                return False, 'pending', tenant
            return False, 'checkout', tenant

        return True, 'active', tenant
    except Tenant.DoesNotExist:
        return True, None, None


@login_required
def dashboard(request):
    """Agency Admin Dashboard with Subscription Payment Gate."""
    is_valid, status_code, tenant = check_agency_subscription(request)
    if not is_valid:
        if status_code == 'pending':
            return redirect('admin_panel:subscription_pending')
        return redirect('admin_panel:subscription_checkout')

    db = get_tenant_db(request)

    total_customers = User.objects.filter(tenant_id=request.user.tenant_id, role=User.Role.CUSTOMER).count()
    total_packages = TravelPackage.objects.using(db).count()
    total_bookings = Booking.objects.using(db).count()
    pending_bookings = Booking.objects.using(db).filter(status='pending').count()
    total_visa_apps = VisaApplication.objects.using(db).count()
    pending_visa_apps = VisaApplication.objects.using(db).filter(status='pending').count()
    total_revenue = Payment.objects.using(db).filter(status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    tenant_id = getattr(request.user, 'tenant_id', None)

    # Candidate Financial Metrics (always use tenant db alias)
    cand_financials = Candidate.objects.using(db).aggregate(
        total_val=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_due=Sum('due_amount')
    )
    total_candidate_collected = cand_financials['total_paid'] or Decimal('0.00')
    total_candidate_due = cand_financials['total_due'] or Decimal('0.00')
    total_candidate_package_val = cand_financials['total_val'] or Decimal('0.00')

    # Visa Lot Quota Stats (always use tenant db alias)
    active_lots = VisaLot.objects.using(db).filter(is_active=True)
    total_remaining_visas = sum(lot.remaining_visas for lot in active_lots)
    total_visa_quota = active_lots.aggregate(total=Sum('quota'))['total'] or 0

    recent_bookings = Booking.objects.using(db).order_by('-booked_at')[:5]
    recent_visa_apps = VisaApplication.objects.using(db).order_by('-submitted_at')[:5]

    # Office Expense Metrics (always use tenant db alias)
    expense_qs = OfficeExpense.objects.using(db).all()
    total_office_expense = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    month_office_expense = expense_qs.filter(
        expense_date__year=timezone.now().year,
        expense_date__month=timezone.now().month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    recent_expenses = expense_qs.order_by('-expense_date')[:5]

    # Package Bookings Financial Metrics
    pkg_booking_qs = Booking.objects.using(db).all()
    booking_total_val = pkg_booking_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    booking_paid_val = pkg_booking_qs.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    booking_due_val = pkg_booking_qs.exclude(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    context = {
        'total_customers': total_customers,
        'total_packages': total_packages,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'booking_total_val': booking_total_val,
        'booking_paid_val': booking_paid_val,
        'booking_due_val': booking_due_val,
        'total_visa_apps': total_visa_apps,
        'pending_visa_apps': pending_visa_apps,
        'total_revenue': total_revenue + total_candidate_collected,
        'total_candidate_collected': total_candidate_collected,
        'total_candidate_due': total_candidate_due,
        'total_candidate_package_val': total_candidate_package_val,
        'total_remaining_visas': total_remaining_visas,
        'total_visa_quota': total_visa_quota,
        'recent_bookings': recent_bookings,
        'recent_visa_apps': recent_visa_apps,
        'total_office_expense': total_office_expense,
        'month_office_expense': month_office_expense,
        'recent_expenses': recent_expenses,
    }
    return render(request, 'admin_panel/dashboard.html', context)


# ── TRAVEL PACKAGES ────────────────────────────────────────────────────────────
@login_required
def package_list(request):
    """List all travel packages for this tenant."""
    db = get_tenant_db(request)
    packages = TravelPackage.objects.using(db).all()
    return render(request, 'admin_panel/packages/list.html', {'packages': packages})


@login_required
def package_create(request):
    """Add a new travel package with photo, connected flight, and connected bus tickets."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import FlightSchedule
    from apps.bus.models import BusSchedule

    flight_schedules = FlightSchedule.objects.using(db).filter(is_active=True)
    bus_schedules = BusSchedule.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        short_description = request.POST.get('short_description', '').strip()
        price = request.POST.get('price', '0')
        discounted_price = request.POST.get('discounted_price', '').strip()
        duration_days = request.POST.get('duration_days', '1')
        available_seats = request.POST.get('available_seats', '20')
        status = request.POST.get('status', 'active')
        flight_schedule_id = request.POST.get('connected_flight_schedule_id', '').strip()
        bus_schedule_id = request.POST.get('connected_bus_schedule_id', '').strip()
        travel_date = request.POST.get('travel_date', '').strip()
        return_date = request.POST.get('return_date', '').strip()

        slug = name.lower().replace(' ', '-').strip()
        base_slug = slug
        count = 1
        while TravelPackage.objects.using(db).filter(slug=slug).exists():
            slug = f"{base_slug}-{count}"
            count += 1

        connected_flight = None
        if flight_schedule_id:
            connected_flight = FlightSchedule.objects.using(db).filter(pk=flight_schedule_id).first()

        connected_bus = None
        if bus_schedule_id:
            connected_bus = BusSchedule.objects.using(db).filter(pk=bus_schedule_id).first()

        pkg = TravelPackage.objects.using(db).create(
            name=name,
            slug=slug,
            description=description,
            short_description=short_description,
            price=Decimal(price if price else '0'),
            discounted_price=Decimal(discounted_price) if discounted_price else None,
            duration_days=int(duration_days if duration_days else '1'),
            total_seats=int(available_seats if available_seats else '20'),
            available_seats=int(available_seats if available_seats else '20'),
            status=status,
            connected_flight_schedule=connected_flight,
            connected_bus_schedule=connected_bus,
            travel_date=travel_date if travel_date else None,
            return_date=return_date if return_date else None,
        )

        if 'featured_image' in request.FILES:
            pkg.featured_image = request.FILES['featured_image']
            pkg.save(using=db)

        if 'gallery_images' in request.FILES:
            for file in request.FILES.getlist('gallery_images'):
                PackageImage.objects.using(db).create(package=pkg, image=file)

        messages.success(request, f'Tour package "{name}" created successfully!')
        return redirect('admin_panel:package_list')

    return render(request, 'admin_panel/packages/create.html', {
        'flight_schedules': flight_schedules,
        'bus_schedules': bus_schedules,
    })


@login_required
def package_edit(request, pk):
    """Edit an existing travel package."""
    db = get_tenant_db(request)
    pkg = get_object_or_404(TravelPackage.objects.using(db), pk=pk)
    from apps.bookings.air_models import FlightSchedule
    from apps.bus.models import BusSchedule

    flight_schedules = FlightSchedule.objects.using(db).filter(is_active=True)
    bus_schedules = BusSchedule.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        pkg.name = request.POST.get('name', '').strip()
        pkg.description = request.POST.get('description', '').strip()
        pkg.short_description = request.POST.get('short_description', '').strip()
        pkg.price = Decimal(request.POST.get('price', '0'))
        disc_price = request.POST.get('discounted_price', '').strip()
        pkg.discounted_price = Decimal(disc_price) if disc_price else None
        pkg.duration_days = int(request.POST.get('duration_days', '1'))
        pkg.total_seats = int(request.POST.get('total_seats', '20'))
        pkg.available_seats = int(request.POST.get('available_seats', '20'))
        pkg.status = request.POST.get('status', 'active')

        travel_date = request.POST.get('travel_date', '').strip()
        return_date = request.POST.get('return_date', '').strip()
        pkg.travel_date = travel_date if travel_date else None
        pkg.return_date = return_date if return_date else None

        flight_schedule_id = request.POST.get('connected_flight_schedule_id', '').strip()
        bus_schedule_id = request.POST.get('connected_bus_schedule_id', '').strip()

        pkg.connected_flight_schedule = FlightSchedule.objects.using(db).filter(pk=flight_schedule_id).first() if flight_schedule_id else None
        pkg.connected_bus_schedule = BusSchedule.objects.using(db).filter(pk=bus_schedule_id).first() if bus_schedule_id else None

        if request.POST.get('remove_featured_image') == '1':
            pkg.featured_image = None

        if 'featured_image' in request.FILES:
            pkg.featured_image = request.FILES['featured_image']

        pkg.save(using=db)

        # Handle removing selected gallery images
        delete_gallery_ids = request.POST.getlist('delete_gallery_images')
        if delete_gallery_ids:
            PackageImage.objects.using(db).filter(pk__in=delete_gallery_ids, package=pkg).delete()

        if 'gallery_images' in request.FILES:
            for file in request.FILES.getlist('gallery_images'):
                PackageImage.objects.using(db).create(package=pkg, image=file)

        messages.success(request, f'Package "{pkg.name}" updated successfully!')
        return redirect('admin_panel:package_list')

    gallery_images = pkg.images.using(db).all() if hasattr(pkg, 'images') else []

    return render(request, 'admin_panel/packages/edit.html', {
        'package': pkg,
        'gallery_images': gallery_images,
        'flight_schedules': flight_schedules,
        'bus_schedules': bus_schedules,
    })


@login_required
def package_gallery_image_delete(request, pk):
    """Delete a single gallery photo from a package."""
    db = get_tenant_db(request)
    img = get_object_or_404(PackageImage.objects.using(db), pk=pk)
    pkg_id = img.package.pk
    img.delete()
    messages.success(request, 'Gallery photo deleted successfully!')
    return redirect('admin_panel:package_edit', pk=pkg_id)


@login_required
def package_delete(request, pk):
    """Delete a travel package."""
    db = get_tenant_db(request)
    pkg = get_object_or_404(TravelPackage.objects.using(db), pk=pk)
    name = pkg.name
    pkg.delete()
    messages.success(request, f'Package "{name}" deleted successfully.')
    return redirect('admin_panel:package_list')


# ── VISA SERVICES ─────────────────────────────────────────────────────────────
@login_required
def visa_service_list(request):
    """List all visa services for this tenant."""
    db = get_tenant_db(request)
    services = VisaService.objects.using(db).all()
    return render(request, 'admin_panel/visa/list.html', {'services': services})


@login_required
def visa_service_create(request):
    """Add a new visa service."""
    db = get_tenant_db(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        visa_type = request.POST.get('visa_type', 'tourist')
        price = request.POST.get('price', '0')
        processing_time = request.POST.get('processing_time', '5-7 business days')
        description = request.POST.get('description', '').strip()

        VisaService.objects.using(db).create(
            name=name,
            visa_type=visa_type,
            price=Decimal(price),
            processing_time=processing_time,
            description=description,
            is_active=True,
        )
        messages.success(request, f'Visa service "{name}" added successfully!')
        return redirect('admin_panel:visa_service_list')

    return render(request, 'admin_panel/visa/create.html')


# ── BOOKINGS & VISA APPLICATIONS ──────────────────────────────────────────────
@login_required
def booking_list(request):
    """List all customer travel bookings & support manual booking."""
    db = get_tenant_db(request)
    bookings = Booking.objects.using(db).all().order_by('-booked_at')
    packages = TravelPackage.objects.using(db).filter(status='active')
    customers = User.objects.filter(tenant_id=request.user.tenant_id, role=User.Role.CUSTOMER)

    booking_paid_val = bookings.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    booking_due_val = bookings.exclude(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    return render(request, 'admin_panel/bookings/list.html', {
        'bookings': bookings,
        'packages': packages,
        'customers': customers,
        'booking_paid_val': booking_paid_val,
        'booking_due_val': booking_due_val,
    })


@login_required
def booking_create(request):
    """Manual booking created by Agency Admin, Staff, or Ambassador."""
    db = get_tenant_db(request)
    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        customer_user_id = request.POST.get('customer_user_id', '').strip()
        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_mobile = request.POST.get('customer_mobile', '').strip()
        travel_date = request.POST.get('travel_date', '').strip()
        number_of_travelers = int(request.POST.get('number_of_travelers', '1'))
        unit_price = Decimal(request.POST.get('unit_price', '0'))
        discount_amount = Decimal(request.POST.get('discount_amount', '0'))
        special_requests = request.POST.get('special_requests', '').strip()
        admin_notes = request.POST.get('admin_notes', '').strip()
        status = request.POST.get('status', 'confirmed')
        payment_status = request.POST.get('payment_status', 'paid')

        pkg = get_object_or_404(TravelPackage.objects.using(db), pk=package_id)

        customer_user = None
        if customer_user_id:
            customer_user = User.objects.filter(pk=customer_user_id, tenant_id=request.user.tenant_id).first()
            if customer_user:
                customer_name = customer_name or f"{customer_user.first_name} {customer_user.last_name}".strip() or customer_user.email
                customer_email = customer_email or customer_user.email
                customer_mobile = customer_mobile or customer_user.mobile

        total_amount = (unit_price * number_of_travelers) - discount_amount
        if total_amount < Decimal('0'):
            total_amount = Decimal('0.00')

        role = Booking.BookedByRole.ADMIN
        if request.user.is_tenant_staff:
            role = Booking.BookedByRole.STAFF
        elif request.user.is_ambassador:
            role = Booking.BookedByRole.AMBASSADOR

        booking = Booking.objects.using(db).create(
            package=pkg,
            customer_user=customer_user,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_mobile=customer_mobile,
            travel_date=travel_date if travel_date else (pkg.travel_date or timezone.now().date()),
            number_of_travelers=number_of_travelers,
            unit_price=unit_price,
            discount_amount=discount_amount,
            total_amount=total_amount,
            booked_by_role=role,
            booked_by_email=request.user.email,
            status=status,
            payment_status=payment_status,
            special_requests=special_requests,
            admin_notes=admin_notes,
        )

        if pkg.available_seats >= number_of_travelers:
            pkg.available_seats -= number_of_travelers
            pkg.booking_count += 1
            pkg.save(using=db)

        messages.success(request, f'Package Booking {booking.booking_code} created successfully!')
        return redirect('admin_panel:booking_invoice', pk=booking.pk)

    return redirect('admin_panel:booking_list')


@login_required
def booking_edit(request, pk):
    """Edit package booking details."""
    db = get_tenant_db(request)
    booking = get_object_or_404(Booking.objects.using(db), pk=pk)
    if request.method == 'POST':
        booking.customer_name = request.POST.get('customer_name', '').strip()
        booking.customer_email = request.POST.get('customer_email', '').strip()
        booking.customer_mobile = request.POST.get('customer_mobile', '').strip()
        booking.travel_date = request.POST.get('travel_date', '').strip()
        booking.number_of_travelers = int(request.POST.get('number_of_travelers', '1'))
        booking.unit_price = Decimal(request.POST.get('unit_price', '0'))
        booking.discount_amount = Decimal(request.POST.get('discount_amount', '0'))
        booking.status = request.POST.get('status', booking.status)
        booking.payment_status = request.POST.get('payment_status', booking.payment_status)
        booking.admin_notes = request.POST.get('admin_notes', '').strip()

        booking.total_amount = (booking.unit_price * booking.number_of_travelers) - booking.discount_amount
        if booking.total_amount < Decimal('0'):
            booking.total_amount = Decimal('0.00')

        booking.save(using=db)
        messages.success(request, f'Booking {booking.booking_code} updated successfully!')
        return redirect('admin_panel:booking_invoice', pk=booking.pk)

    return redirect('admin_panel:booking_list')


@login_required
def booking_delete(request, pk):
    """Delete a package booking."""
    db = get_tenant_db(request)
    booking = get_object_or_404(Booking.objects.using(db), pk=pk)
    code = booking.booking_code
    booking.delete()
    messages.success(request, f'Booking {code} has been deleted.')
    return redirect('admin_panel:booking_list')


@login_required
def booking_invoice(request, pk):
    """Printable & Editable Invoice view for Agency Admin / Staff."""
    db = get_tenant_db(request)
    booking = get_object_or_404(Booking.objects.using(db), pk=pk)
    tenant = Tenant.objects.filter(slug=request.user.tenant_id).first() if request.user.tenant_id else None

    if request.method == 'POST':
        booking.customer_name = request.POST.get('customer_name', booking.customer_name).strip()
        booking.customer_email = request.POST.get('customer_email', booking.customer_email).strip()
        booking.customer_mobile = request.POST.get('customer_mobile', booking.customer_mobile).strip()
        booking.unit_price = Decimal(request.POST.get('unit_price', str(booking.unit_price)))
        booking.number_of_travelers = int(request.POST.get('number_of_travelers', str(booking.number_of_travelers)))
        booking.discount_amount = Decimal(request.POST.get('discount_amount', str(booking.discount_amount)))
        booking.status = request.POST.get('status', booking.status)
        booking.payment_status = request.POST.get('payment_status', booking.payment_status)
        booking.admin_notes = request.POST.get('admin_notes', booking.admin_notes).strip()

        booking.total_amount = (booking.unit_price * booking.number_of_travelers) - booking.discount_amount
        if booking.total_amount < Decimal('0'):
            booking.total_amount = Decimal('0.00')

        booking.save(using=db)
        messages.success(request, f'Invoice for {booking.booking_code} updated successfully!')
        return redirect('admin_panel:booking_invoice', pk=booking.pk)

    return render(request, 'admin_panel/bookings/invoice.html', {
        'booking': booking,
        'tenant': tenant,
    })


@login_required
def booking_update_status(request, pk, status):
    """Update status of a booking."""
    db = get_tenant_db(request)
    booking = get_object_or_404(Booking.objects.using(db), pk=pk)
    booking.status = status
    booking.save(using=db)
    messages.success(request, f'Booking {booking.booking_code} status updated to {status}.')
    return redirect('admin_panel:booking_list')


@login_required
def booking_update_payment_status(request, pk, payment_status):
    """Approve / update payment status for a booking (e.g. paid, pending, unpaid)."""
    db = get_tenant_db(request)
    booking = get_object_or_404(Booking.objects.using(db), pk=pk)
    booking.payment_status = payment_status
    if payment_status == 'paid' and booking.status == 'pending':
        booking.status = 'confirmed'
    booking.save(using=db)
    messages.success(request, f'Payment status for Booking {booking.booking_code} updated to "{payment_status.title()}".')
    return redirect('admin_panel:booking_list')


@login_required
def visa_app_list(request):
    """List all customer visa applications."""
    db = get_tenant_db(request)
    applications = VisaApplication.objects.using(db).all()
    return render(request, 'admin_panel/visa/applications.html', {'applications': applications})


@login_required
def visa_app_update_status(request, pk, status):
    """Update status of a visa application."""
    db = get_tenant_db(request)
    app = get_object_or_404(VisaApplication.objects.using(db), pk=pk)
    app.status = status
    app.save(using=db)
    messages.success(request, f'Visa application {app.application_code} status updated to {status}.')
    return redirect('admin_panel:visa_app_list')


# ── CUSTOMER USER MANAGEMENT ──────────────────────────────────────────────────
@login_required
def customer_list(request):
    """List all registered customers for this tenant."""
    customers = User.objects.filter(tenant_id=request.user.tenant_id, role=User.Role.CUSTOMER)
    return render(request, 'admin_panel/customers/list.html', {'customers': customers})


@login_required
def customer_create(request):
    """Agency Admin creates a new customer user manually."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'admin_panel/customers/create.html')

        user = User.objects.create_user(
            email=email,
            password=password or '123456',
            first_name=first_name,
            last_name=last_name,
            mobile=mobile,
            role=User.Role.CUSTOMER,
            tenant_id=request.user.tenant_id,
            email_verified=True,
        )
        messages.success(request, f'Customer account "{user.email}" registered successfully!')
        return redirect('admin_panel:customer_list')

    return render(request, 'admin_panel/customers/create.html')


@login_required
def customer_toggle_ban(request, pk):
    """Toggle ban status for a customer."""
    user = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id)
    user.is_banned = not user.is_banned
    user.save()
    status_str = 'banned' if user.is_banned else 'activated'
    messages.success(request, f'Customer {user.email} has been {status_str}.')
    return redirect('admin_panel:customer_list')


# ── STAFF MANAGEMENT ──────────────────────────────────────────────────────────
@login_required
def staff_list(request):
    """List all staff members for this agency."""
    # Only tenant admin can manage staff
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to manage staff.')
        return redirect('admin_panel:dashboard')
    staff_members = User.objects.filter(
        tenant_id=request.user.tenant_id,
        role=User.Role.TENANT_STAFF,
    )
    return render(request, 'admin_panel/staff/list.html', {'staff_members': staff_members})


@login_required
def staff_create(request):
    """Agency Admin creates a new staff member."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to create staff accounts.')
        return redirect('admin_panel:dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        mobile     = request.POST.get('mobile', '').strip()
        password   = request.POST.get('password', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'admin_panel/staff/create.html')

        user = User.objects.create_user(
            email=email,
            password=password or 'StaffPass@123',
            first_name=first_name,
            last_name=last_name,
            mobile=mobile,
            role=User.Role.TENANT_STAFF,
            tenant_id=request.user.tenant_id,
            email_verified=True,
            is_staff=True,
        )
        messages.success(request, f'Staff account "{user.email}" created successfully!')
        return redirect('admin_panel:staff_list')

    return render(request, 'admin_panel/staff/create.html')


@login_required
def staff_toggle_ban(request, pk):
    """Toggle active/banned status for a staff member."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('admin_panel:staff_list')
    staff = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id, role=User.Role.TENANT_STAFF)
    staff.is_banned = not staff.is_banned
    staff.save()
    status_str = 'suspended' if staff.is_banned else 'activated'
    messages.success(request, f'Staff member {staff.email} has been {status_str}.')
    return redirect('admin_panel:staff_list')


@login_required
def staff_delete(request, pk):
    """Delete a staff member account."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to delete staff accounts.')
        return redirect('admin_panel:staff_list')
    staff = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id, role=User.Role.TENANT_STAFF)
    email = staff.email
    staff.delete()
    messages.success(request, f'Staff account "{email}" has been removed.')
    return redirect('admin_panel:staff_list')


# ── WEBSITE CMS MANAGEMENT & AGENCY BRANDING ──────────────────────────────────
@login_required
def cms_settings(request):
    """Manage Tenant Website Hero, Agency Logo, Agency Name & CMS Content."""
    db = get_tenant_db(request)
    hero = HeroSection.objects.using(db).first()
    tenant = None
    if request.user.tenant_id:
        tenant = Tenant.objects.filter(slug=request.user.tenant_id).first()

    if request.method == 'POST':
        hero_title = request.POST.get('hero_title', '').strip()
        hero_subtitle = request.POST.get('hero_subtitle', '').strip()
        agency_name = request.POST.get('agency_name', '').strip()

        # Update Hero Section
        if hero:
            hero.title = hero_title
            hero.subtitle = hero_subtitle
            hero.save(using=db)
        else:
            HeroSection.objects.using(db).create(
                title=hero_title,
                subtitle=hero_subtitle,
                is_active=True,
            )

        # Update Agency Name & Logo
        if tenant:
            if agency_name:
                tenant.agency_name = agency_name
            if 'logo' in request.FILES:
                tenant.logo = request.FILES['logo']
            tenant.save()

        messages.success(request, 'Website CMS & Agency Branding settings saved successfully!')
        return redirect('admin_panel:cms_settings')

    return render(request, 'admin_panel/cms/settings.html', {'hero': hero, 'tenant': tenant})


@login_required
def domain_settings(request):
    """View & Manage Agency Subdomain, Automated Database Routing Info, and Custom Domains."""
    from apps.tenants.models import TenantDomain
    tenant = None
    domains = []
    if request.user.tenant_id:
        tenant = Tenant.objects.filter(slug=request.user.tenant_id).first()
        if tenant:
            domains = TenantDomain.objects.filter(tenant=tenant)

    if request.method == 'POST' and tenant:
        custom_domain = request.POST.get('custom_domain', '').strip().lower()
        if custom_domain:
            if TenantDomain.objects.filter(domain=custom_domain).exists():
                messages.error(request, f'The domain "{custom_domain}" is already registered in the platform.')
            else:
                TenantDomain.objects.create(
                    tenant=tenant,
                    domain=custom_domain,
                    domain_type=TenantDomain.DomainType.CUSTOM,
                    status=TenantDomain.Status.PENDING,
                    is_primary=False,
                )
                messages.success(request, f'Custom domain "{custom_domain}" registered successfully! DNS verification pending.')
                return redirect('admin_panel:domain_settings')

    return render(request, 'admin_panel/domains/settings.html', {'tenant': tenant, 'domains': domains, 'BASE_DOMAIN': getattr(settings, 'BASE_DOMAIN', 'localhost:8000')})


# ── SUBSCRIPTION PAYMENT GATE VIEWS ──────────────────────────────────────────
@login_required
def subscription_checkout(request):
    """Agency Subscription Payment Checkout View."""
    if not request.user.tenant_id:
        return redirect('admin_panel:dashboard')

    tenant = get_object_or_404(Tenant, slug=request.user.tenant_id)
    packages = SubscriptionPackage.objects.filter(is_active=True)

    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        transaction_id = request.POST.get('transaction_id', '').strip()
        payment_method = request.POST.get('payment_method', 'bKash / Bank Transfer')

        package = get_object_or_404(SubscriptionPackage, id=package_id)

        # Create or update subscription record with PENDING_PAYMENT status
        sub, _ = Subscription.objects.get_or_create(
            tenant=tenant,
            defaults={
                'package': package,
                'billing_cycle': 'monthly',
                'start_date': timezone.now(),
                'end_date': timezone.now() + timezone.timedelta(days=30),
                'status': Subscription.Status.PENDING_PAYMENT,
            }
        )
        sub.package = package
        sub.status = Subscription.Status.PENDING_PAYMENT
        sub.save()

        # Create Pending SaaS Payment Record for Super Admin Approval
        SaaSPayment.objects.create(
            tenant=tenant,
            subscription=sub,
            package=package,
            transaction_id=transaction_id or f'TXN-{tenant.id}-{timezone.now().strftime("%Y%m%d%H%M")}',
            amount=package.monthly_price,
            currency='BDT',
            payment_method=payment_method,
            billing_cycle='monthly',
            status=SaaSPayment.Status.PENDING,
        )

        messages.info(request, '📩 Payment submitted! Awaiting Super Admin review and approval.')
        return redirect('admin_panel:subscription_pending')

    return render(request, 'admin_panel/subscription/checkout.html', {'tenant': tenant, 'packages': packages})


@login_required
def subscription_pending(request):
    """Agency Subscription Payment Pending Approval View - Auto-redirects when approved."""
    if not request.user.tenant_id:
        return redirect('admin_panel:dashboard')

    tenant = get_object_or_404(Tenant, slug=request.user.tenant_id)

    # Check if payment was already approved by Super Admin
    approved_payment = SaaSPayment.objects.filter(tenant=tenant, status='paid').order_by('-created_at').first()
    sub = tenant.subscriptions.order_by('-created_at').first()

    if tenant.status == Tenant.Status.ACTIVE and sub and sub.status == Subscription.Status.ACTIVE:
        # Payment approved! Redirect with success handshake message
        messages.success(
            request,
            f'🎉 Congratulations! Your subscription has been approved and activated by the Super Admin. '
            f'Welcome to <strong>{tenant.agency_name}</strong> Agency Dashboard!'
        )
        return redirect('admin_panel:dashboard')

    # Still pending — show payment pending screen
    pending_payment = SaaSPayment.objects.filter(tenant=tenant, status='pending').order_by('-created_at').first()

    return render(request, 'admin_panel/subscription/pending.html', {
        'tenant': tenant,
        'payment': pending_payment,
    })


@login_required
def my_subscription(request):
    """View active subscription plan details and payments for the agency."""
    if not request.user.tenant_id:
        return redirect('admin_panel:dashboard')

    tenant = get_object_or_404(Tenant, slug=request.user.tenant_id)
    subscription = tenant.subscriptions.order_by('-created_at').first()
    if subscription:
        subscription.check_and_update_status()

    payments = SaaSPayment.objects.filter(tenant=tenant).order_by('-created_at')

    return render(request, 'admin_panel/subscription/my_subscription.html', {
        'tenant': tenant,
        'subscription': subscription,
        'payments': payments,
    })


@login_required
def domain_settings(request):
    """Agency Domain Management: Subdomain URL and Custom Domain Setup."""
    if not request.user.tenant_id:
        return redirect('admin_panel:dashboard')

    tenant = get_object_or_404(Tenant, slug=request.user.tenant_id)
    sub = tenant.subscriptions.order_by('-created_at').first()
    
    # Check if subscription allows custom domain
    custom_domain_allowed = sub and sub.package and sub.package.custom_domain

    # Auto-ensure default subdomain record exists
    raw_subdomain = f"{tenant.slug}.{getattr(settings, 'BASE_DOMAIN', 'localhost:8000')}"
    clean_subdomain = raw_subdomain.split(':')[0]
    
    subdomain_obj, _ = TenantDomain.objects.get_or_create(
        tenant=tenant,
        domain_type=TenantDomain.DomainType.SUBDOMAIN,
        defaults={
            'domain': clean_subdomain,
            'is_primary': True,
            'status': TenantDomain.Status.ACTIVE,
        }
    )
    # Ensure domain is updated if previously stored with port
    if subdomain_obj.domain != clean_subdomain:
        subdomain_obj.domain = clean_subdomain
        subdomain_obj.save(update_fields=['domain'])

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_custom_domain':
            if not custom_domain_allowed:
                messages.error(request, "Your current subscription plan does not support Custom Domains. Please upgrade to Professional or Enterprise.")
                return redirect('admin_panel:domain_settings')
            
            raw_domain = request.POST.get('custom_domain', '').strip().lower()
            raw_domain = raw_domain.replace('https://', '').replace('http://', '').strip('/')
            
            if not raw_domain:
                messages.error(request, "Please enter a valid domain name.")
            elif TenantDomain.objects.filter(domain=raw_domain).exclude(tenant=tenant).exists():
                messages.error(request, "This custom domain is already registered by another agency.")
            else:
                domain_obj, created = TenantDomain.objects.get_or_create(
                    tenant=tenant,
                    domain=raw_domain,
                    defaults={
                        'domain_type': TenantDomain.DomainType.CUSTOM,
                        'status': TenantDomain.Status.PENDING,
                        'is_primary': False,
                    }
                )
                if created:
                    messages.success(request, f"Custom domain {raw_domain} added! Please configure your DNS CNAME / A record.")
                else:
                    messages.info(request, f"Custom domain {raw_domain} updated.")
            return redirect('admin_panel:domain_settings')

        elif action == 'delete_domain':
            domain_id = request.POST.get('domain_id')
            d = get_object_or_404(TenantDomain, id=domain_id, tenant=tenant)
            if d.domain_type == TenantDomain.DomainType.SUBDOMAIN:
                messages.error(request, "Default subdirectory / subdomain cannot be deleted.")
            else:
                d.delete()
                messages.success(request, "Custom domain removed successfully.")
            return redirect('admin_panel:domain_settings')

    domains = tenant.domains.all()

    return render(request, 'admin_panel/settings/domain_settings.html', {
        'tenant': tenant,
        'domains': domains,
        'subdomain_str': raw_subdomain,
        'custom_domain_allowed': custom_domain_allowed,
        'base_domain': getattr(settings, 'BASE_DOMAIN', 'localhost:8000'),
    })


@login_required
def agency_support(request):
    """Live Chat & Ticket Support Desk for Agency to communicate with Super Admin."""
    from apps.support.models import AgencySupportTicket, AgencySupportMessage

    if not request.user.tenant_id:
        return redirect('admin_panel:dashboard')

    tenant = get_object_or_404(Tenant, slug=request.user.tenant_id)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()
        priority = request.POST.get('priority', 'medium')

        ticket = AgencySupportTicket.objects.create(
            tenant=tenant,
            subject=subject,
            priority=priority,
            status=AgencySupportTicket.Status.OPEN,
        )
        AgencySupportMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role='tenant_admin',
            message=message_text,
        )
        messages.success(request, f'Support ticket "{subject}" created successfully! Super Admin notified.')
        return redirect('admin_panel:agency_support')

    tickets = AgencySupportTicket.objects.filter(tenant=tenant).order_by('-created_at')
    return render(request, 'admin_panel/support/agency_support.html', {
        'tenant': tenant,
        'tickets': tickets,
    })


# ── FEATURE LIMIT CHECKER ───────────────────────────────────────────────────
def check_feature_limit(request, feature_key):
    """
    Check if agency tenant's subscription permits a feature or numerical limit.
    feature_key: 'max_staff', 'max_ambassadors', 'max_bus_routes', 'max_air_routes', 'bus_ticket_enabled', 'air_ticket_enabled'
    """
    if request.user.is_super_admin or 'support_mode_tenant_id' in request.session:
        return True, ""

    if not request.user.tenant_id:
        return True, ""

    try:
        tenant = Tenant.objects.get(slug=request.user.tenant_id)
        sub = tenant.subscriptions.order_by('-created_at').first()
        if not sub or not sub.package:
            return True, ""

        pkg = sub.package

        if feature_key == 'bus_ticket_enabled' and not getattr(pkg, 'bus_ticket_enabled', True):
            return False, "Bus Ticket system is not included in your current subscription plan. Please upgrade your plan."

        if feature_key == 'air_ticket_enabled' and not getattr(pkg, 'air_ticket_enabled', True):
            return False, "Air Ticket system is not included in your current subscription plan. Please upgrade your plan."

        if feature_key == 'max_ambassadors' and getattr(pkg, 'max_ambassadors', -1) != -1:
            current_count = User.objects.filter(tenant_id=request.user.tenant_id, role=User.Role.AMBASSADOR).count()
            if current_count >= pkg.max_ambassadors:
                return False, f"You have reached the maximum allowed Ambassadors ({pkg.max_ambassadors}) for your subscription plan."

        if feature_key == 'max_staff' and getattr(pkg, 'max_staff', -1) != -1:
            current_count = User.objects.filter(tenant_id=request.user.tenant_id, role=User.Role.TENANT_STAFF).count()
            if current_count >= pkg.max_staff:
                return False, f"You have reached the maximum allowed Staff accounts ({pkg.max_staff}) for your subscription plan."

        return True, ""
    except Tenant.DoesNotExist:
        return True, ""


# ── AMBASSADOR MANAGEMENT ────────────────────────────────────────────────────
@login_required
def ambassador_list(request):
    """List all ambassadors for this agency."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to manage ambassadors.')
        return redirect('admin_panel:dashboard')
    ambassadors = User.objects.filter(
        tenant_id=request.user.tenant_id,
        role=User.Role.AMBASSADOR,
    )
    return render(request, 'admin_panel/ambassador/list.html', {'ambassadors': ambassadors})


@login_required
def ambassador_create(request):
    """Agency Admin creates a new Ambassador account with subscription check."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'You do not have permission to create ambassador accounts.')
        return redirect('admin_panel:dashboard')

    is_allowed, msg = check_feature_limit(request, 'max_ambassadors')
    if not is_allowed:
        messages.error(request, msg)
        return redirect('admin_panel:ambassador_list')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        mobile     = request.POST.get('mobile', '').strip()
        password   = request.POST.get('password', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'admin_panel/ambassador/create.html')

        user = User.objects.create_user(
            email=email,
            password=password or 'AmbassadorPass@123',
            first_name=first_name,
            last_name=last_name,
            mobile=mobile,
            role=User.Role.AMBASSADOR,
            tenant_id=request.user.tenant_id,
            email_verified=True,
            is_staff=True,
        )
        messages.success(request, f'Ambassador account "{user.email}" created successfully!')
        return redirect('admin_panel:ambassador_list')

    return render(request, 'admin_panel/ambassador/create.html')


@login_required
def ambassador_toggle_ban(request, pk):
    """Toggle status of ambassador."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'Permission denied.')
        return redirect('admin_panel:ambassador_list')
    user = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id, role=User.Role.AMBASSADOR)
    user.is_banned = not user.is_banned
    user.save()
    status_str = 'suspended' if user.is_banned else 'activated'
    messages.success(request, f'Ambassador {user.email} has been {status_str}.')
    return redirect('admin_panel:ambassador_list')


@login_required
def ambassador_delete(request, pk):
    """Delete ambassador account."""
    if not (request.user.is_tenant_admin or request.user.is_super_admin):
        messages.error(request, 'Permission denied.')
        return redirect('admin_panel:ambassador_list')
    user = get_object_or_404(User, pk=pk, tenant_id=request.user.tenant_id, role=User.Role.AMBASSADOR)
    email = user.email
    user.delete()
    messages.success(request, f'Ambassador "{email}" has been deleted.')
    return redirect('admin_panel:ambassador_list')


# ── BUS TICKET SYSTEM ─────────────────────────────────────────────────────────
@login_required
def bus_operator_list(request):
    """List & manage bus operators."""
    is_allowed, msg = check_feature_limit(request, 'bus_ticket_enabled')
    if not is_allowed:
        messages.error(request, msg)
        return redirect('admin_panel:dashboard')

    db = get_tenant_db(request)
    from apps.bus.models import BusOperator
    operators = BusOperator.objects.using(db).all()
    return render(request, 'admin_panel/bus/operators.html', {'operators': operators})


@login_required
def bus_operator_create(request):
    """Add a new bus operator."""
    db = get_tenant_db(request)
    from apps.bus.models import BusOperator
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('contact_phone', '').strip()
        email = request.POST.get('contact_email', '').strip()
        address = request.POST.get('address', '').strip()
        desc = request.POST.get('description', '').strip()

        op = BusOperator.objects.using(db).create(
            name=name, contact_phone=phone, contact_email=email,
            address=address, description=desc, is_active=True
        )
        if 'logo' in request.FILES:
            op.logo = request.FILES['logo']
            op.save(using=db)

        messages.success(request, f'Bus Operator "{name}" created successfully!')
        return redirect('admin_panel:bus_operator_list')
    return redirect('admin_panel:bus_operator_list')


@login_required
def bus_operator_delete(request, pk):
    """Delete bus operator."""
    db = get_tenant_db(request)
    from apps.bus.models import BusOperator
    op = get_object_or_404(BusOperator.objects.using(db), pk=pk)
    name = op.name
    op.delete()
    messages.success(request, f'Bus operator "{name}" deleted.')
    return redirect('admin_panel:bus_operator_list')


@login_required
def bus_route_list(request):
    """List & manage bus routes."""
    db = get_tenant_db(request)
    from apps.bus.models import BusOperator, BusRoute
    routes = BusRoute.objects.using(db).all()
    operators = BusOperator.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        op_id = request.POST.get('operator_id')
        from_city = request.POST.get('from_city', '').strip()
        to_city = request.POST.get('to_city', '').strip()
        duration = request.POST.get('estimated_duration', '').strip()

        op = get_object_or_404(BusOperator.objects.using(db), pk=op_id)
        BusRoute.objects.using(db).create(
            operator=op, from_city=from_city, to_city=to_city, estimated_duration=duration
        )
        messages.success(request, f'Bus Route {from_city} → {to_city} created successfully!')
        return redirect('admin_panel:bus_route_list')

    return render(request, 'admin_panel/bus/routes.html', {'routes': routes, 'operators': operators})


@login_required
def bus_route_delete(request, pk):
    """Delete bus route."""
    db = get_tenant_db(request)
    from apps.bus.models import BusRoute
    route = get_object_or_404(BusRoute.objects.using(db), pk=pk)
    route.delete()
    messages.success(request, 'Bus route deleted.')
    return redirect('admin_panel:bus_route_list')


@login_required
def bus_schedule_list(request):
    """List & create bus schedules."""
    db = get_tenant_db(request)
    from apps.bus.models import BusRoute, BusSchedule
    schedules = BusSchedule.objects.using(db).all()
    routes = BusRoute.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        route_id = request.POST.get('route_id')
        dep_time = request.POST.get('departure_time')
        arr_time = request.POST.get('arrival_time')
        seat_class = request.POST.get('seat_class', 'economy')
        price = request.POST.get('price', '0')
        total_seats = request.POST.get('total_seats', '40')

        route = get_object_or_404(BusRoute.objects.using(db), pk=route_id)
        BusSchedule.objects.using(db).create(
            route=route, departure_time=dep_time, arrival_time=arr_time,
            seat_class=seat_class, price=Decimal(price),
            total_seats=int(total_seats), available_seats=int(total_seats)
        )
        messages.success(request, f'Bus schedule added for {route}!')
        return redirect('admin_panel:bus_schedule_list')

    return render(request, 'admin_panel/bus/schedules.html', {'schedules': schedules, 'routes': routes})


@login_required
def bus_schedule_delete(request, pk):
    """Delete bus schedule."""
    db = get_tenant_db(request)
    from apps.bus.models import BusSchedule
    sch = get_object_or_404(BusSchedule.objects.using(db), pk=pk)
    sch.delete()
    messages.success(request, 'Bus schedule deleted.')
    return redirect('admin_panel:bus_schedule_list')


@login_required
def bus_booking_list(request):
    """View & create bus bookings by admin, staff, or ambassador."""
    db = get_tenant_db(request)
    from apps.bus.models import BusSchedule, BusBooking
    bookings = BusBooking.objects.using(db).all()
    schedules = BusSchedule.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        sch_id = request.POST.get('schedule_id')
        cust_name = request.POST.get('customer_name', '').strip()
        cust_email = request.POST.get('customer_email', '').strip()
        cust_mobile = request.POST.get('customer_mobile', '').strip()
        passenger_count = int(request.POST.get('passenger_count', '1'))
        seat_numbers = request.POST.get('seat_numbers', '').strip()

        sch = get_object_or_404(BusSchedule.objects.using(db), pk=sch_id)
        unit_price = sch.price
        total_amount = unit_price * passenger_count

        role = BusBooking.BookedByRole.ADMIN
        if request.user.is_tenant_staff:
            role = BusBooking.BookedByRole.STAFF
        elif request.user.is_ambassador:
            role = BusBooking.BookedByRole.AMBASSADOR

        b = BusBooking.objects.using(db).create(
            schedule=sch,
            customer_name=cust_name,
            customer_email=cust_email,
            customer_mobile=cust_mobile,
            passenger_count=passenger_count,
            seat_numbers=seat_numbers,
            unit_price=unit_price,
            total_amount=total_amount,
            booked_by_role=role,
            booked_by_email=request.user.email,
            status=BusBooking.Status.CONFIRMED,
            payment_status=BusBooking.PaymentStatus.PAID,
        )

        # reduce seats
        if sch.available_seats >= passenger_count:
            sch.available_seats -= passenger_count
            sch.save(using=db)

        messages.success(request, f'Bus Booking {b.booking_code} created successfully!')
        return redirect('admin_panel:bus_booking_list')

    return render(request, 'admin_panel/bus/bookings.html', {'bookings': bookings, 'schedules': schedules})


@login_required
def bus_booking_update_status(request, pk, status):
    """Update bus booking status."""
    db = get_tenant_db(request)
    from apps.bus.models import BusBooking
    booking = get_object_or_404(BusBooking.objects.using(db), pk=pk)
    booking.status = status
    booking.save(using=db)
    messages.success(request, f'Bus Booking {booking.booking_code} status set to {status}.')
    return redirect('admin_panel:bus_booking_list')


# ── AIR TICKET SYSTEM ─────────────────────────────────────────────────────────
@login_required
def airline_list(request):
    """List & manage airlines."""
    is_allowed, msg = check_feature_limit(request, 'air_ticket_enabled')
    if not is_allowed:
        messages.error(request, msg)
        return redirect('admin_panel:dashboard')

    db = get_tenant_db(request)
    from apps.bookings.air_models import Airline
    airlines = Airline.objects.using(db).all()
    return render(request, 'admin_panel/air/airlines.html', {'airlines': airlines})


@login_required
def airline_create(request):
    """Add a new airline."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import Airline
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        phone = request.POST.get('contact_phone', '').strip()
        email = request.POST.get('contact_email', '').strip()
        website = request.POST.get('website', '').strip()

        al = Airline.objects.using(db).create(
            name=name, code=code, contact_phone=phone, contact_email=email, website=website, is_active=True
        )
        if 'logo' in request.FILES:
            al.logo = request.FILES['logo']
            al.save(using=db)

        messages.success(request, f'Airline "{name}" created successfully!')
        return redirect('admin_panel:airline_list')
    return redirect('admin_panel:airline_list')


@login_required
def airline_delete(request, pk):
    """Delete airline."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import Airline
    al = get_object_or_404(Airline.objects.using(db), pk=pk)
    name = al.name
    al.delete()
    messages.success(request, f'Airline "{name}" deleted.')
    return redirect('admin_panel:airline_list')


@login_required
def flight_route_list(request):
    """List & manage flight routes."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import Airline, FlightRoute
    routes = FlightRoute.objects.using(db).all()
    airlines = Airline.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        al_id = request.POST.get('airline_id')
        flight_num = request.POST.get('flight_number', '').strip()
        from_city = request.POST.get('from_city', '').strip()
        from_code = request.POST.get('from_airport_code', '').strip().upper()
        to_city = request.POST.get('to_city', '').strip()
        to_code = request.POST.get('to_airport_code', '').strip().upper()

        al = get_object_or_404(Airline.objects.using(db), pk=al_id)
        FlightRoute.objects.using(db).create(
            airline=al, flight_number=flight_num, from_city=from_city,
            from_airport_code=from_code, to_city=to_city, to_airport_code=to_code
        )
        messages.success(request, f'Flight Route {from_city} ({from_code}) → {to_city} ({to_code}) created!')
        return redirect('admin_panel:flight_route_list')

    return render(request, 'admin_panel/air/routes.html', {'routes': routes, 'airlines': airlines})


@login_required
def flight_route_delete(request, pk):
    """Delete flight route."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import FlightRoute
    route = get_object_or_404(FlightRoute.objects.using(db), pk=pk)
    route.delete()
    messages.success(request, 'Flight route deleted.')
    return redirect('admin_panel:flight_route_list')


@login_required
def flight_schedule_list(request):
    """List & create flight schedules."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import FlightRoute, FlightSchedule
    schedules = FlightSchedule.objects.using(db).all()
    routes = FlightRoute.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        route_id = request.POST.get('route_id')
        dep_time = request.POST.get('departure_datetime')
        arr_time = request.POST.get('arrival_datetime')
        cabin_class = request.POST.get('cabin_class', 'economy')
        price = request.POST.get('price', '0')
        total_seats = request.POST.get('total_seats', '150')
        baggage = request.POST.get('baggage_allowance', '23kg').strip()

        route = get_object_or_404(FlightRoute.objects.using(db), pk=route_id)
        FlightSchedule.objects.using(db).create(
            route=route, departure_datetime=dep_time, arrival_datetime=arr_time,
            cabin_class=cabin_class, price=Decimal(price),
            total_seats=int(total_seats), available_seats=int(total_seats),
            baggage_allowance=baggage
        )
        messages.success(request, f'Flight schedule added for {route}!')
        return redirect('admin_panel:flight_schedule_list')

    return render(request, 'admin_panel/air/schedules.html', {'schedules': schedules, 'routes': routes})


@login_required
def flight_schedule_delete(request, pk):
    """Delete flight schedule."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import FlightSchedule
    sch = get_object_or_404(FlightSchedule.objects.using(db), pk=pk)
    sch.delete()
    messages.success(request, 'Flight schedule deleted.')
    return redirect('admin_panel:flight_schedule_list')


@login_required
def air_booking_list(request):
    """View & create Air Ticket bookings by admin, staff, or ambassador."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import FlightSchedule, AirTicketBooking
    bookings = AirTicketBooking.objects.using(db).all()
    schedules = FlightSchedule.objects.using(db).filter(is_active=True)

    if request.method == 'POST':
        sch_id = request.POST.get('schedule_id')
        cust_name = request.POST.get('customer_name', '').strip()
        cust_email = request.POST.get('customer_email', '').strip()
        cust_mobile = request.POST.get('customer_mobile', '').strip()
        passport_num = request.POST.get('passport_number', '').strip().upper()
        pnr_num = request.POST.get('pnr_number', '').strip().upper()
        passenger_count = int(request.POST.get('passenger_count', '1'))

        sch = get_object_or_404(FlightSchedule.objects.using(db), pk=sch_id)
        unit_price = sch.price
        total_amount = unit_price * passenger_count

        role = AirTicketBooking.BookedByRole.ADMIN
        if request.user.is_tenant_staff:
            role = AirTicketBooking.BookedByRole.STAFF
        elif request.user.is_ambassador:
            role = AirTicketBooking.BookedByRole.AMBASSADOR

        b = AirTicketBooking.objects.using(db).create(
            schedule=sch,
            customer_name=cust_name,
            customer_email=cust_email,
            customer_mobile=cust_mobile,
            passport_number=passport_num,
            pnr_number=pnr_num,
            passenger_count=passenger_count,
            unit_price=unit_price,
            total_amount=total_amount,
            booked_by_role=role,
            booked_by_email=request.user.email,
            status=AirTicketBooking.Status.CONFIRMED,
            payment_status=AirTicketBooking.PaymentStatus.PAID,
        )

        if sch.available_seats >= passenger_count:
            sch.available_seats -= passenger_count
            sch.save(using=db)

        messages.success(request, f'Air Ticket Booking {b.booking_code} created successfully!')
        return redirect('admin_panel:air_booking_list')

    return render(request, 'admin_panel/air/bookings.html', {'bookings': bookings, 'schedules': schedules})


@login_required
def air_booking_update_status(request, pk, status):
    """Update air ticket booking status."""
    db = get_tenant_db(request)
    from apps.bookings.air_models import AirTicketBooking
    booking = get_object_or_404(AirTicketBooking.objects.using(db), pk=pk)
    booking.status = status
    booking.save(using=db)
    messages.success(request, f'Air Ticket Booking {booking.booking_code} status set to {status}.')
    return redirect('admin_panel:air_booking_list')



"""
apps/tenants/public_views.py

Customer-facing public travel agency website views.
- On the MAIN domain (no request.tenant): shows the Softobro Travel SaaS marketing page
  with subscription plans and platform features.
- On an AGENCY subdomain/custom domain (request.tenant exists): shows that agency's own
  CMS website with their specific tour packages and visa services.
"""
from django.shortcuts import render, redirect
from django.contrib import messages

from apps.travel_packages.models import TravelPackage
from apps.visa.models import VisaService
from apps.destinations.models import Destination
from apps.cms.models import HeroSection, Testimonial, FAQ
from apps.subscriptions.models import SubscriptionPackage
from apps.tenants.agency_models import VisaLot


from django.conf import settings

def tenant_db(request):
    """Return database alias for current tenant in public views."""
    tenant = getattr(request, 'tenant', None)
    if tenant:
        db_alias = f'tenant_{tenant.slug}'
        if db_alias not in settings.DATABASES:
            settings.DATABASES[db_alias] = tenant.get_db_config()
        from apps.tenants.routers import set_tenant_db
        set_tenant_db(db_alias)
        return db_alias
    return 'default'


def home(request):
    """
    Home view:
    - No tenant → Softobro Travel main SaaS marketing page (subscription plans + features)
    - Has tenant → Agency's own website (tour packages, visa services, hero CMS)
    """
    if not getattr(request, 'tenant', None):
        # ── Main Platform Home: SaaS marketing / subscription plans ──────────
        packages = SubscriptionPackage.objects.filter(is_active=True).order_by('sort_order', 'monthly_price')
        return render(request, 'website/home.html', {
            'subscription_packages': packages,
            'is_platform_home': True,
        })

    # ── Agency Website Home: powered by per-tenant CMS ───────────────────────
    db = tenant_db(request)

    try:
        hero = HeroSection.objects.using(db).filter(is_active=True).first()
    except Exception:
        hero = None

    try:
        packages = list(TravelPackage.objects.using(db).filter(status='active')[:6])
    except Exception:
        packages = []

    try:
        visa_lots = list(VisaLot.objects.filter(is_active=True, show_on_website=True)[:4])
        if not visa_lots:
            visa_lots = list(VisaService.objects.using(db).filter(is_active=True)[:4])
    except Exception:
        visa_lots = []

    try:
        destinations = list(Destination.objects.using(db).filter(is_active=True)[:4])
    except Exception:
        destinations = []

    try:
        testimonials = list(Testimonial.objects.using(db).filter(is_active=True)[:3])
    except Exception:
        testimonials = []

    try:
        faqs = list(FAQ.objects.using(db).filter(is_active=True)[:5])
    except Exception:
        faqs = []

    context = {
        'hero': hero,
        'packages': packages,
        'visas': visa_lots,
        'destinations': destinations,
        'testimonials': testimonials,
        'faqs': faqs,
        'is_platform_home': False,
    }
    return render(request, 'website/home.html', context)


def packages_list(request):
    """Agency Website Packages Listing (only accessible on agency subdomains)."""
    db = tenant_db(request)
    packages = TravelPackage.objects.using(db).filter(status='active')
    return render(request, 'website/packages.html', {'packages': packages})


def package_detail(request, slug):
    """Agency Website Package Detail view."""
    db = tenant_db(request)
    from django.shortcuts import get_object_or_404
    pkg = get_object_or_404(TravelPackage.objects.using(db), slug=slug)
    images = pkg.images.using(db).all() if hasattr(pkg, 'images') else []
    return render(request, 'website/package_detail.html', {
        'package': pkg,
        'images': images,
    })


def package_book(request, slug):
    """Customer Package Booking Flow under current Agency."""
    from decimal import Decimal
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from apps.bookings.models import Booking

    if not getattr(request, 'tenant', None):
        messages.error(request, "Package booking is only available on an agency website.")
        return redirect('public:home')

    db = tenant_db(request)
    pkg = get_object_or_404(TravelPackage.objects.using(db), slug=slug)
    tenant = request.tenant

    # Check Customer Auth under this specific Agency
    if not request.user.is_authenticated or getattr(request.user, 'tenant_id', None) != tenant.slug:
        messages.info(
            request,
            f"🔒 To book '{pkg.name}', please log in or create an account under {tenant.agency_name}."
        )
        login_url = f"/auth/login/?next=/packages/{pkg.slug}/book/&tenant={tenant.slug}"
        return redirect(login_url)

    if request.method == 'POST':
        number_of_travelers = int(request.POST.get('number_of_travelers', '1'))
        travel_date = request.POST.get('travel_date', '').strip()
        special_requests = request.POST.get('special_requests', '').strip()

        unit_price = pkg.effective_price
        total_amount = unit_price * number_of_travelers

        booking = Booking.objects.using(db).create(
            package=pkg,
            customer_user=request.user,
            customer_name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
            customer_email=request.user.email,
            customer_mobile=request.user.mobile,
            travel_date=travel_date if travel_date else (pkg.travel_date or timezone.now().date()),
            number_of_travelers=number_of_travelers,
            unit_price=unit_price,
            discount_amount=Decimal('0.00'),
            total_amount=total_amount,
            booked_by_role=Booking.BookedByRole.CUSTOMER,
            booked_by_email=request.user.email,
            status=Booking.Status.PENDING,
            payment_status=Booking.PaymentStatus.PENDING,
            special_requests=special_requests,
        )

        if pkg.available_seats >= number_of_travelers:
            pkg.available_seats -= number_of_travelers
            pkg.booking_count += 1
            pkg.save(using=db)

        messages.success(request, f"🎉 Booking created successfully! Your Booking Reference is {booking.booking_code}.")
        return redirect('public:customer_bookings')

    return render(request, 'website/package_booking.html', {
        'package': pkg,
        'tenant': tenant,
    })


def visa_list(request):
    """Agency Website Visa Listings — shows active VisaLots with show_on_website=True."""
    db = tenant_db(request)
    try:
        visa_lots = list(VisaLot.objects.filter(is_active=True, show_on_website=True))
        fallback = list(VisaService.objects.using(db).filter(is_active=True)) if not visa_lots else []
    except Exception:
        visa_lots, fallback = [], []
    return render(request, 'website/visa.html', {'visa_lots': visa_lots, 'services': fallback})


def about(request):
    """About Us Page."""
    return render(request, 'website/about.html')


def contact(request):
    """Contact Us Page."""
    if request.method == 'POST':
        messages.success(request, 'Thank you for reaching out! We will contact you shortly.')
        return redirect('public:contact')
    return render(request, 'website/contact.html')

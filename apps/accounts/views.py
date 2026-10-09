"""
apps/accounts/views.py

Authentication views for ViserTrip:
  - Login (Super Admin, Tenant Admin, Staff, Customer)
  - Agency SaaS Signup (Registers new Tenant + Admin user)
  - Logout
  - Password Reset
"""
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User
from apps.tenants.models import Tenant, TenantDomain, GlobalSetting
from apps.subscriptions.models import SubscriptionPackage, Subscription
from apps.tenants.provisioning import provision_tenant


def user_login(request):
    """Unified Login View for Super Admin, Tenant Admin & Customers."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        next_url = request.POST.get('next', '').strip() or request.GET.get('next', '').strip()

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if not user.is_active or user.is_banned:
                messages.error(request, 'Your account has been deactivated or banned. Please contact support.')
                return render(request, 'auth/login.html')

            # Block tenant admins/staff if their agency is not yet approved
            if user.is_tenant_admin or user.is_tenant_staff:
                from apps.tenants.models import Tenant
                tenant_obj = Tenant.objects.filter(slug=user.tenant_id).first()
                if tenant_obj and tenant_obj.status not in ('active', 'trial'):
                    messages.warning(
                        request,
                        f'Your agency "{tenant_obj.agency_name}" is pending approval by the platform admin. '
                        'You will receive an email once your account is approved and ready to use.'
                    )
                    return render(request, 'auth/login.html')

            login(request, user)
            messages.success(request, f'Welcome back, {user.full_name}!')

            # Redirect based on next param first, then user role
            if next_url:
                return redirect(next_url)
            if user.is_super_admin:
                return redirect('superadmin:dashboard')
            elif user.is_tenant_admin or user.is_tenant_staff:
                return redirect('admin_panel:dashboard')
            else:
                return redirect('public:home')
        else:
            messages.error(request, 'Invalid email or password.')

    next_url = request.GET.get('next', '')
    return render(request, 'auth/login.html', {'next': next_url})


def agency_register(request):
    """
    Agency Registration View (SaaS Signup).
    Creates Tenant record and triggers database provisioning.
    """
    packages = SubscriptionPackage.objects.filter(is_active=True)
    bkash_setting = GlobalSetting.objects.filter(key='bkash_number').first()
    bkash_number = bkash_setting.value if bkash_setting else '0186982XXXX'

    if request.method == 'POST':
        agency_name = request.POST.get('agency_name', '').strip()
        owner_name = request.POST.get('owner_name', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '').strip()
        package_id = request.POST.get('package_id')

        bkash_trx_id = request.POST.get('bkash_trx_id', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'auth/agency_register.html', {
                'packages': packages,
                'bkash_number': bkash_number
            })

        try:
            package = SubscriptionPackage.objects.get(id=package_id)
        except SubscriptionPackage.DoesNotExist:
            package = packages.first()

        # Step 1: Create Tenant Record (pending approval)
        tenant = Tenant.objects.create(
            agency_name=agency_name,
            owner_name=owner_name,
            email=email,
            mobile=mobile,
            status=Tenant.Status.PENDING,
        )

        # Step 2: Create Trial Subscription
        subscription = Subscription.objects.create(
            tenant=tenant,
            package=package,
            billing_cycle='trial',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=package.trial_days),
            status='trial',
        )

        # Step 3: Record bKash SaaS Payment
        if bkash_trx_id:
            from apps.subscriptions.models import SaaSPayment
            SaaSPayment.objects.create(
                tenant=tenant,
                subscription=subscription,
                package=package,
                transaction_id=bkash_trx_id,
                amount=package.monthly_price if package else Decimal('0.00'),
                payment_method='bKash',
                billing_cycle='monthly',
                status=SaaSPayment.Status.PENDING,
            )

        # Step 4: Provision Tenant Database
        provision_tenant(tenant, admin_email=email, admin_password=password)

        messages.success(
            request,
            f'Your travel agency "{agency_name}" has been registered successfully! '
            'Our team will review and approve your account shortly. '
            'You\'ll be able to log in once approved.'
        )
        return redirect('accounts:login')

    return render(request, 'auth/agency_register.html', {
        'packages': packages,
        'bkash_number': bkash_number
    })


def user_logout(request):
    """User Logout View."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


def customer_register(request):
    """
    Customer Self-Registration on an Agency Website.
    Creates a Customer-role user scoped to the current tenant agency.
    Only available on agency subdomains (request.tenant must exist).
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, 'Customer registration is only available on an agency website.')
        return redirect('accounts:login')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        mobile     = request.POST.get('mobile', '').strip()
        password   = request.POST.get('password', '').strip()
        confirm_pw = request.POST.get('confirm_password', '').strip()

        if password != confirm_pw:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/customer_register.html', {'tenant': tenant})

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'auth/customer_register.html', {'tenant': tenant})

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            mobile=mobile,
            role=User.Role.CUSTOMER,
            tenant_id=tenant.slug,
            email_verified=True,
        )

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome, {user.full_name}! Your account has been created.')

        next_url = request.GET.get('next', '/')
        return redirect(next_url)

    return render(request, 'auth/customer_register.html', {'tenant': tenant})


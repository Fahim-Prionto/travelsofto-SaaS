"""
apps/superadmin/views.py

Super Admin Dashboard & Management Views for ViserTrip SaaS Platform.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.utils import timezone

from apps.accounts.models import User
from apps.tenants.models import Tenant, TenantDomain, TenantProvisioningLog
from apps.tenants.provisioning import provision_tenant
from apps.subscriptions.models import SubscriptionPackage, Subscription, SaaSPayment


def superadmin_required(user):
    return user.is_authenticated and user.is_super_admin


@login_required
@user_passes_test(superadmin_required)
def dashboard(request):
    """Super Admin Global SaaS Dashboard."""

    # Key Platform Metrics
    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status=Tenant.Status.ACTIVE).count()
    inactive_tenants = Tenant.objects.filter(status=Tenant.Status.INACTIVE).count()
    suspended_tenants = Tenant.objects.filter(status=Tenant.Status.SUSPENDED).count()
    trial_tenants = Tenant.objects.filter(status=Tenant.Status.TRIAL).count()
    expired_subscriptions = Subscription.objects.filter(status=Subscription.Status.EXPIRED).count()

    total_customers = User.objects.filter(role=User.Role.CUSTOMER).count()

    # Revenue Stats
    total_revenue = SaaSPayment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0

    now = timezone.now()
    monthly_revenue = SaaSPayment.objects.filter(
        status='paid',
        paid_at__month=now.month,
        paid_at__year=now.year,
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_domains = TenantDomain.objects.count()
    active_domains = TenantDomain.objects.filter(status='active').count()

    recent_tenants = Tenant.objects.select_related('admin_user').order_by('-created_at')[:5]
    recent_payments = SaaSPayment.objects.select_related('tenant').order_by('-created_at')[:5]

    context = {
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'inactive_tenants': inactive_tenants,
        'suspended_tenants': suspended_tenants,
        'trial_tenants': trial_tenants,
        'expired_subscriptions': expired_subscriptions,
        'total_customers': total_customers,
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'total_domains': total_domains,
        'active_domains': active_domains,
        'recent_tenants': recent_tenants,
        'recent_payments': recent_payments,
    }
    return render(request, 'superadmin/dashboard.html', context)


@login_required
@user_passes_test(superadmin_required)
def tenant_list(request):
    """List all registered tenants with filtering."""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')

    tenants = Tenant.objects.select_related('admin_user').all()

    if status_filter:
        tenants = tenants.filter(status=status_filter)
    if query:
        tenants = tenants.filter(agency_name__icontains=query) | tenants.filter(email__icontains=query)

    context = {
        'tenants': tenants,
        'status_filter': status_filter,
        'query': query,
    }
    return render(request, 'superadmin/tenants/list.html', context)


@login_required
@user_passes_test(superadmin_required)
def tenant_create(request):
    """Super Admin create new Agency Tenant directly."""
    packages = SubscriptionPackage.objects.filter(is_active=True)

    if request.method == 'POST':
        agency_name = request.POST.get('agency_name', '').strip()
        owner_name = request.POST.get('owner_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        package_id = request.POST.get('package_id')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'superadmin/tenants/create.html', {'packages': packages})

        try:
            package = SubscriptionPackage.objects.get(id=package_id)
        except SubscriptionPackage.DoesNotExist:
            package = packages.first()

        # Create Tenant Record
        tenant = Tenant.objects.create(
            agency_name=agency_name,
            owner_name=owner_name,
            email=email,
            status=Tenant.Status.ACTIVE,
        )

        # Create Subscription
        Subscription.objects.create(
            tenant=tenant,
            package=package,
            billing_cycle='monthly',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            status='active',
        )

        # Provision Tenant Database & Create Admin User
        provision_tenant(tenant, admin_email=email, admin_password=password)

        messages.success(request, f'✅ Agency "{agency_name}" successfully created and provisioned!')
        return redirect('superadmin:tenant_list')

    return render(request, 'superadmin/tenants/create.html', {'packages': packages})


@login_required
@user_passes_test(superadmin_required)
def tenant_delete(request, slug):
    """Super Admin delete an Agency Tenant account."""
    tenant = get_object_or_404(Tenant, slug=slug)
    agency_name = tenant.agency_name

    if request.method == 'POST':
        # Remove admin user if tied
        if tenant.admin_user:
            tenant.admin_user.delete()
        tenant.delete()
        messages.success(request, f'🗑️ Agency Tenant "{agency_name}" deleted successfully.')
        return redirect('superadmin:tenant_list')

    return render(request, 'superadmin/tenants/delete_confirm.html', {'tenant': tenant})


@login_required
@user_passes_test(superadmin_required)
def tenant_support_login(request, slug):
    """Super Admin support mode: Enter tenant's agency dashboard directly to support them."""
    tenant = get_object_or_404(Tenant, slug=slug)
    
    # Store tenant context in session so tenant middleware routes correctly
    request.session['support_mode_tenant_id'] = str(tenant.id)
    messages.info(request, f'🎧 Entered Support Assistance Mode for agency: "{tenant.agency_name}".')
    return redirect('admin_panel:dashboard')



@login_required
@user_passes_test(superadmin_required)
def tenant_detail(request, slug):
    """Tenant detailed view with subscription history & logs."""
    tenant = get_object_or_404(Tenant, slug=slug)
    subscriptions = tenant.subscriptions.select_related('package').all()
    payments = tenant.saas_payments.all()
    logs = tenant.provisioning_logs.all()[:20]
    domains = tenant.domains.all()

    context = {
        'tenant': tenant,
        'subscriptions': subscriptions,
        'payments': payments,
        'logs': logs,
        'domains': domains,
    }
    return render(request, 'superadmin/tenants/detail.html', context)


@login_required
@user_passes_test(superadmin_required)
def package_list(request):
    """SaaS Subscription Packages management."""
    packages = SubscriptionPackage.objects.all()
    return render(request, 'superadmin/packages/list.html', {'packages': packages})


@login_required
@user_passes_test(superadmin_required)
def package_edit(request, pk):
    """Edit a SaaS Subscription Package."""
    package = get_object_or_404(SubscriptionPackage, pk=pk)

    if request.method == 'POST':
        # Basic Info
        package.name = request.POST.get('name', package.name)
        package.description = request.POST.get('description', package.description)
        package.badge_color = request.POST.get('badge_color', package.badge_color)

        # Pricing
        package.monthly_price = request.POST.get('monthly_price', package.monthly_price)
        package.yearly_price = request.POST.get('yearly_price', package.yearly_price)
        package.trial_days = int(request.POST.get('trial_days', package.trial_days))

        # Feature Limits
        package.max_users = int(request.POST.get('max_users', package.max_users))
        package.max_travel_packages = int(request.POST.get('max_travel_packages', package.max_travel_packages))
        package.max_visa_services = int(request.POST.get('max_visa_services', package.max_visa_services))
        package.max_staff = int(request.POST.get('max_staff', package.max_staff))
        package.storage_limit_mb = int(request.POST.get('storage_limit_mb', package.storage_limit_mb))

        # Feature Flags
        package.custom_domain = 'custom_domain' in request.POST
        package.advanced_analytics = 'advanced_analytics' in request.POST
        package.advanced_cms = 'advanced_cms' in request.POST
        package.priority_support = 'priority_support' in request.POST
        package.api_access = 'api_access' in request.POST
        package.white_label = 'white_label' in request.POST
        package.is_active = 'is_active' in request.POST
        package.is_recommended = 'is_recommended' in request.POST
        package.sort_order = int(request.POST.get('sort_order', package.sort_order))

        package.save()
        messages.success(request, f'✅ "{package.name}" plan updated successfully!')
        return redirect('superadmin:package_list')

    return render(request, 'superadmin/packages/edit.html', {'package': package})


@login_required
@user_passes_test(superadmin_required)
def analytics(request):
    """Global platform analytics page."""
    return render(request, 'superadmin/analytics.html')


@login_required
@user_passes_test(superadmin_required)
def domain_management(request):
    """Domain & subdomain management for all tenants."""
    status_filter = request.GET.get('status', '')
    domains = TenantDomain.objects.select_related('tenant').all()
    if status_filter:
        domains = domains.filter(status=status_filter)

    total_domains = domains.count()
    active_domains = TenantDomain.objects.filter(status='active').count()
    pending_domains = TenantDomain.objects.filter(status='pending').count()

    context = {
        'domains': domains,
        'status_filter': status_filter,
        'total_domains': total_domains,
        'active_domains': active_domains,
        'pending_domains': pending_domains,
    }
    return render(request, 'superadmin/domains/list.html', context)


@login_required
@user_passes_test(superadmin_required)
def saas_payments(request):
    """SaaS subscription payment records across all tenants."""
    status_filter = request.GET.get('status', '')
    payments = SaaSPayment.objects.select_related('tenant', 'subscription__package').order_by('-created_at')

    if status_filter:
        payments = payments.filter(status=status_filter)

    total_revenue = SaaSPayment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0
    pending_amount = SaaSPayment.objects.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
    failed_count = SaaSPayment.objects.filter(status='failed').count()

    context = {
        'payments': payments,
        'status_filter': status_filter,
        'total_revenue': total_revenue,
        'pending_amount': pending_amount,
        'failed_count': failed_count,
    }
    return render(request, 'superadmin/payments/list.html', context)


@login_required
@user_passes_test(superadmin_required)
def approve_saas_payment(request, payment_id):
    """Super Admin approves agency payment -> automatically activates tenant subscription."""
    payment = get_object_or_404(SaaSPayment, id=payment_id)
    payment.status = SaaSPayment.Status.PAID
    payment.paid_at = timezone.now()
    payment.save()

    # Automatically activate or extend subscription
    if payment.subscription:
        subscription = payment.subscription
        subscription.status = Subscription.Status.ACTIVE
        subscription.amount_paid = payment.amount
        subscription.start_date = timezone.now()
        # Extend end_date by 30 days or 365 days based on billing cycle
        days = 365 if payment.billing_cycle == 'yearly' else 30
        subscription.end_date = timezone.now() + timezone.timedelta(days=days)
        subscription.save()

    # Ensure Tenant status is active
    tenant = payment.tenant
    tenant.status = Tenant.Status.ACTIVE
    tenant.save()

    messages.success(request, f'✅ Payment for "{tenant.agency_name}" APPROVED! Subscription activated automatically.')
    return redirect('superadmin:saas_payments')


@login_required
@user_passes_test(superadmin_required)
def reject_saas_payment(request, payment_id):
    """Super Admin rejects agency payment."""
    payment = get_object_or_404(SaaSPayment, id=payment_id)
    payment.status = SaaSPayment.Status.FAILED
    payment.save()

    if payment.subscription:
        payment.subscription.status = Subscription.Status.PENDING_PAYMENT
        payment.subscription.save()

    messages.warning(request, f'⚠️ Payment for "{payment.tenant.agency_name}" rejected.')
    return redirect('superadmin:saas_payments')



@login_required
@user_passes_test(superadmin_required)
def support_tickets(request):
    """Super Admin & Supporter Live Chat Support Monitoring & Ticket Dashboard."""
    from apps.support.models import AgencySupportTicket, AgencySupportMessage

    status_filter = request.GET.get('status', '')
    tickets = AgencySupportTicket.objects.select_related('tenant', 'assigned_supporter').all()

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    open_count = AgencySupportTicket.objects.filter(status=AgencySupportTicket.Status.OPEN).count()
    in_progress_count = AgencySupportTicket.objects.filter(status=AgencySupportTicket.Status.IN_PROGRESS).count()
    closed_count = AgencySupportTicket.objects.filter(status=AgencySupportTicket.Status.CLOSED).count()

    context = {
        'tickets': tickets,
        'status_filter': status_filter,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'closed_count': closed_count,
        'support_members': User.objects.filter(role=User.Role.SUPPORT_MEMBER),
    }
    return render(request, 'superadmin/support/list.html', context)


@login_required
@user_passes_test(superadmin_required)
def support_chat(request, ticket_id):
    """Live Chat System between Super Admin/Supporter and Travel Agency."""
    from apps.support.models import AgencySupportTicket, AgencySupportMessage

    ticket = get_object_or_404(AgencySupportTicket, id=ticket_id)

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        if message_text:
            AgencySupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                sender_type=AgencySupportMessage.SenderType.SUPER_ADMIN,
                sender_name=request.user.get_full_name() or request.user.email,
                message=message_text,
            )
            ticket.status = AgencySupportTicket.Status.REPLIED
            ticket.save()
            messages.success(request, 'Reply sent to agency.')
            return redirect('superadmin:support_chat', ticket_id=ticket.id)

    messages_list = ticket.messages.select_related('sender').all()

    context = {
        'ticket': ticket,
        'chat_messages': messages_list,
    }
    return render(request, 'superadmin/support/chat.html', context)


@login_required
@user_passes_test(superadmin_required)
def support_members(request):
    """Super Admin create and manage Support Team Members."""
    support_team = User.objects.filter(role=User.Role.SUPPORT_MEMBER)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, 'A user with this email already exists.')
        else:
            User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.SUPPORT_MEMBER,
                is_staff=True
            )
            messages.success(request, f'✅ Support Team Member "{first_name} {last_name}" created successfully!')
            return redirect('superadmin:support_members')

    return render(request, 'superadmin/support/members.html', {'support_team': support_team})



@login_required
@user_passes_test(superadmin_required)
def profile(request):
    """Super Admin Profile and Password Update View."""
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.phone = request.POST.get('phone', '').strip()
            user.save()
            messages.success(request, '✅ Profile details updated successfully!')
            return redirect('superadmin:profile')

        elif action == 'change_password':
            from django.contrib.auth import update_session_auth_hash
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_password) < 6:
                messages.error(request, 'New password must be at least 6 characters long.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, '✅ Password changed successfully!')
                return redirect('superadmin:profile')

    return render(request, 'superadmin/profile.html', {'user': user})


@login_required
@user_passes_test(superadmin_required)
def global_settings(request):
    """Super Admin Global Settings (e.g. bKash Number for SaaS Platform)."""
    from apps.tenants.models import GlobalSetting

    bkash_obj, _ = GlobalSetting.objects.get_or_create(key='bkash_number', defaults={'value': '0186982XXXX'})

    if request.method == 'POST':
        bkash_number = request.POST.get('bkash_number', '').strip()
        bkash_obj.value = bkash_number
        bkash_obj.save()
        messages.success(request, '✅ Global settings updated successfully!')
        return redirect('superadmin:global_settings')

    context = {
        'bkash_number': bkash_obj.value,
    }
    return render(request, 'superadmin/global_settings.html', context)

"""
apps/superadmin/views.py

Super Admin Dashboard & Management Views for ViserTrip SaaS Platform.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, Count, Q
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
    now = timezone.now()

    # 1. Auto-sync expired subscriptions so dashboard statuses are 100% live in real time
    try:
        stale_subs = Subscription.objects.filter(
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIAL],
            end_date__lte=now
        )
        for sub in stale_subs:
            sub.check_and_update_status()
    except Exception:
        pass

    # 2. Key Platform Metrics
    total_tenants = Tenant.objects.count()

    # Active trial subscriptions (ongoing trial period)
    trial_tenant_ids = set(
        Subscription.objects.filter(
            Q(status=Subscription.Status.TRIAL) | Q(billing_cycle=Subscription.BillingCycle.TRIAL),
            end_date__gt=now
        ).values_list('tenant_id', flat=True)
    )

    trial_tenants = Tenant.objects.filter(
        Q(status=Tenant.Status.TRIAL) | Q(id__in=trial_tenant_ids)
    ).distinct().count()

    active_tenants = Tenant.objects.filter(
        Q(status=Tenant.Status.ACTIVE) | Q(id__in=trial_tenant_ids)
    ).distinct().count()

    inactive_tenants = Tenant.objects.filter(status=Tenant.Status.INACTIVE).count()
    suspended_tenants = Tenant.objects.filter(status=Tenant.Status.SUSPENDED).count()

    # Expired Subscriptions: status is expired OR end_date has passed
    expired_subscriptions = Subscription.objects.filter(
        Q(status=Subscription.Status.EXPIRED) | Q(end_date__lte=now)
    ).count()

    # Total Platform Users: Registered customer users across agencies + agency candidate users
    customer_users_count = User.objects.filter(role=User.Role.CUSTOMER).count()
    try:
        from apps.tenants.agency_models import Candidate
        candidates_count = Candidate.objects.count()
    except Exception:
        candidates_count = 0
    total_customers = customer_users_count + candidates_count

    # Revenue Stats
    total_revenue = SaaSPayment.objects.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0

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
    """List all registered tenants with filtering. Also auto-syncs stale tenant statuses."""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    now = timezone.now()

    # Auto-sync first: check subscriptions and fix stale statuses
    try:
        for sub in Subscription.objects.filter(status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIAL], end_date__lte=now):
            sub.check_and_update_status()
    except Exception:
        pass

    tenants = Tenant.objects.select_related('admin_user').all()

    if status_filter:
        if status_filter == 'trial':
            trial_tenant_ids = set(
                Subscription.objects.filter(
                    Q(status=Subscription.Status.TRIAL) | Q(billing_cycle=Subscription.BillingCycle.TRIAL),
                    end_date__gt=now
                ).values_list('tenant_id', flat=True)
            )
            tenants = tenants.filter(Q(status=Tenant.Status.TRIAL) | Q(id__in=trial_tenant_ids))
        else:
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
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '').strip()
        package_id = request.POST.get('package_id')
        billing_type = request.POST.get('billing_type', 'trial')  # trial | monthly | yearly

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'superadmin/tenants/create.html', {'packages': packages})

        try:
            package = SubscriptionPackage.objects.get(id=package_id)
        except SubscriptionPackage.DoesNotExist:
            package = packages.first()

        # ── Determine billing cycle, dates, and status ──────────────────────
        now = timezone.now()
        if billing_type == 'trial':
            trial_days = package.trial_days or 14
            trial_end = now + timezone.timedelta(days=trial_days)
            sub_status = Subscription.Status.TRIAL
            tenant_status = Tenant.Status.TRIAL
            billing_cycle = Subscription.BillingCycle.TRIAL
            start_date = now
            end_date = trial_end
            trial_ends_at = trial_end
        elif billing_type == 'yearly':
            sub_status = Subscription.Status.ACTIVE
            tenant_status = Tenant.Status.ACTIVE
            billing_cycle = Subscription.BillingCycle.YEARLY
            start_date = now
            end_date = now + timezone.timedelta(days=365)
            trial_ends_at = None
        else:  # monthly (default)
            sub_status = Subscription.Status.ACTIVE
            tenant_status = Tenant.Status.ACTIVE
            billing_cycle = Subscription.BillingCycle.MONTHLY
            start_date = now
            end_date = now + timezone.timedelta(days=30)
            trial_ends_at = None

        # Create Tenant Record
        tenant = Tenant.objects.create(
            agency_name=agency_name,
            owner_name=owner_name,
            email=email,
            mobile=mobile,
            status=tenant_status,
        )

        # Create Subscription
        Subscription.objects.create(
            tenant=tenant,
            package=package,
            billing_cycle=billing_cycle,
            start_date=start_date,
            end_date=end_date,
            trial_ends_at=trial_ends_at,
            status=sub_status,
        )

        # Provision Tenant Database & Create Admin User
        provision_tenant(tenant, admin_email=email, admin_password=password)

        type_label = '🆓 Trial' if billing_type == 'trial' else '✅ Active'
        messages.success(request, f'{type_label} Agency "{agency_name}" successfully created and provisioned!')
        return redirect('superadmin:tenant_list')

    return render(request, 'superadmin/tenants/create.html', {'packages': packages})



@login_required
@user_passes_test(superadmin_required)
def tenant_delete(request, slug):
    """Super Admin delete an Agency Tenant account."""
    tenant = get_object_or_404(Tenant, slug=slug)
    agency_name = tenant.agency_name

    if request.method == 'POST':
        from apps.tenants.routers import set_tenant_db
        from django.db import connection, transaction
        from django.db.utils import ProgrammingError

        db_alias = f'tenant_{tenant.slug}'
        
        # Ensure DB is mapped
        if db_alias not in settings.DATABASES:
            settings.DATABASES[db_alias] = tenant.get_db_config()
            
        set_tenant_db(db_alias)
        
        try:
            # We wrap the standard Django deletion in atomic so if it fails, the transaction is cleanly rolled back
            # and we can fall back to raw deletion without breaking the current DB connection state.
            with transaction.atomic():
                if tenant.admin_user:
                    tenant.admin_user.delete()
                tenant.delete()
            messages.success(request, f'🗑️ Agency Tenant "{agency_name}" deleted successfully.')
            
        except Exception as e:
            # If standard delete fails due to missing relation (tenant was never migrated)
            import logging
            logging.error(f"Tenant delete cascade failed: {e}. Falling back to force raw-delete.")
            
            # Reset tenant context back to public before executing raw SQL
            set_tenant_db('default')
            
            try:
                with connection.cursor() as cursor:
                    def safe_delete(query, params):
                        try:
                            with transaction.atomic():
                                cursor.execute(query, params)
                        except Exception as sqle:
                            logging.warning(f"Ignored cleanup error on '{query}': {sqle}")

                    # 1. Delete dependent SaaS payments
                    safe_delete("DELETE FROM subscriptions_saaspayment WHERE tenant_id = %s", [tenant.id])
                    # 2. Delete tenant subscriptions
                    safe_delete("DELETE FROM subscriptions_subscription WHERE tenant_id = %s", [tenant.id])
                    # 3. Delete tenant domains
                    safe_delete("DELETE FROM tenants_tenantdomain WHERE tenant_id = %s", [tenant.id])
                    # 4. Delete tenant support tickets & messages if support tables exist
                    safe_delete("DELETE FROM support_agencysupportmessage WHERE ticket_id IN (SELECT id FROM support_agencysupportticket WHERE tenant_id = %s)", [tenant.id])
                    safe_delete("DELETE FROM support_agencysupportticket WHERE tenant_id = %s", [tenant.id])
                    # 5. Delete tenant provisioning logs
                    safe_delete("DELETE FROM tenants_tenantprovisioninglog WHERE tenant_id = %s", [tenant.id])
                    # 6. Unlink admin_user from tenant
                    admin_user_id = tenant.admin_user_id
                    if admin_user_id:
                        safe_delete("UPDATE tenants_tenant SET admin_user_id = NULL WHERE id = %s", [tenant.id])
                    # 7. Delete Tenant record itself
                    cursor.execute("DELETE FROM tenants_tenant WHERE id = %s", [tenant.id])
                    # 8. Delete Admin User record
                    if admin_user_id:
                        safe_delete("DELETE FROM accounts_user WHERE id = %s", [admin_user_id])
                    # 9. Drop isolated PostgreSQL schema completely
                    safe_delete(f'DROP SCHEMA IF EXISTS "{tenant.db_name}" CASCADE;', [])
                
                messages.success(request, f'🗑️ Agency "{agency_name}" deleted successfully.')
            except Exception as force_e:
                messages.error(request, f"Critical error during force delete: {str(force_e)}")
                
        finally:
            set_tenant_db('default')
            
        return redirect('superadmin:tenant_list')

    return render(request, 'superadmin/tenants/delete_confirm.html', {'tenant': tenant})


@login_required
@user_passes_test(superadmin_required)
def tenant_approve(request, slug):
    """Approve a pending agency tenant so they can log in."""
    tenant = get_object_or_404(Tenant, slug=slug)

    if tenant.status in (Tenant.Status.ACTIVE, Tenant.Status.TRIAL):
        messages.info(request, f'Agency "{tenant.agency_name}" is already active.')
        return redirect('superadmin:tenant_list')

    sub = tenant.subscriptions.order_by('-created_at').first()
    now = timezone.now()
    if sub and (sub.status == Subscription.Status.TRIAL or sub.billing_cycle == Subscription.BillingCycle.TRIAL) and sub.end_date > now:
        tenant.status = Tenant.Status.TRIAL
    else:
        tenant.status = Tenant.Status.ACTIVE
    tenant.save(update_fields=['status'])

    # Notify the agency owner
    try:
        from django.core.mail import send_mail
        send_mail(
            subject='Your Agency Account Has Been Approved! 🎉',
            message=f"""Hello {tenant.owner_name},

Great news! Your travel agency "{tenant.agency_name}" has been reviewed and approved by our team.

You can now log in to your admin panel at:
{tenant.admin_url}

Best regards,
The Platform Team""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[tenant.email],
            fail_silently=True,
        )
    except Exception:
        pass

    messages.success(request, f'✅ Agency "{tenant.agency_name}" has been approved and is now active!')
    return redirect('superadmin:tenant_list')


@login_required
@user_passes_test(superadmin_required)
def tenant_toggle_status(request, slug):
    """Toggle an agency tenant status between Active and Suspended/Disabled."""
    tenant = get_object_or_404(Tenant, slug=slug)
    if tenant.status == Tenant.Status.ACTIVE:
        tenant.status = Tenant.Status.SUSPENDED
        messages.warning(request, f'🛑 Agency "{tenant.agency_name}" has been SUSPENDED / DISABLED.')
    else:
        tenant.status = Tenant.Status.ACTIVE
        messages.success(request, f'✅ Agency "{tenant.agency_name}" has been ACTIVATED / ENABLED.')
    
    tenant.save(update_fields=['status'])
    return redirect(request.META.get('HTTP_REFERER', 'superadmin:tenant_list'))


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
    """Tenant detailed view with subscription history, resource usage & logs."""
    tenant = get_object_or_404(Tenant, slug=slug)
    subscriptions = tenant.subscriptions.select_related('package').all()
    payments = tenant.saas_payments.all()
    logs = tenant.provisioning_logs.all()[:20]
    domains = tenant.domains.all()

    # ── Compute per-agency resource usage stats ─────────────────────────────
    active_sub = tenant.subscriptions.select_related('package').order_by('-end_date').first()
    usage_stats = None

    if active_sub and active_sub.package:
        from apps.accounts.models import User as TenantUser
        pkg = active_sub.package

        # Auto-expire if needed
        active_sub.check_and_update_status()

        current_customers = TenantUser.objects.filter(
            tenant_id=tenant.slug, role=TenantUser.Role.CUSTOMER
        ).count()
        current_staff = TenantUser.objects.filter(
            tenant_id=tenant.slug, role=TenantUser.Role.TENANT_STAFF
        ).count()

        # Read tenant-isolated DB for package/visa counts
        from apps.travel_packages.models import TravelPackage
        from apps.visa.models import VisaService
        db_alias = f'tenant_{tenant.slug}'
        if db_alias not in settings.DATABASES:
            try:
                settings.DATABASES[db_alias] = tenant.get_db_config()
            except Exception:
                db_alias = 'default'
        try:
            current_packages = TravelPackage.objects.using(db_alias).count()
        except Exception:
            current_packages = 0
        try:
            current_visa = VisaService.objects.using(db_alias).count()
        except Exception:
            current_visa = 0

        def pct(used, limit):
            if limit == -1 or limit == 0:
                return 100 if limit == 0 else 0
            return min(round(used / limit * 100), 100)

        usage_stats = {
            'subscription': active_sub,
            'plan': pkg,
            'days_remaining': active_sub.days_remaining,
            'end_date': active_sub.end_date,
            'status': active_sub.status,
            # Customers
            'current_customers': current_customers,
            'max_customers': pkg.max_users,
            'customers_pct': pct(current_customers, pkg.max_users),
            # Packages
            'current_packages': current_packages,
            'max_packages': pkg.max_travel_packages,
            'packages_pct': pct(current_packages, pkg.max_travel_packages),
            # Visa
            'current_visa': current_visa,
            'max_visa': pkg.max_visa_services,
            'visa_pct': pct(current_visa, pkg.max_visa_services),
            # Staff
            'current_staff': current_staff,
            'max_staff': pkg.max_staff,
            'staff_pct': pct(current_staff, pkg.max_staff),
        }

    # ── Check if this tenant ever had a trial (trial-once enforcement) ──────
    trial_used = tenant.subscriptions.filter(billing_cycle='trial').exists()
    packages = SubscriptionPackage.objects.filter(is_active=True)

    # ── Handle Superadmin: Renew / Extend Subscription ───────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'renew_subscription':
        billing_type = request.POST.get('billing_type', 'monthly')
        package_id   = request.POST.get('package_id')

        # Enforce trial-once rule
        if billing_type == 'trial' and trial_used:
            messages.error(
                request,
                f'⚠️ Agency "{tenant.agency_name}" already used their free trial. '
                'Only Monthly or Yearly renewal is allowed.'
            )
            return redirect('superadmin:tenant_detail', slug=tenant.slug)

        try:
            pkg = SubscriptionPackage.objects.get(id=package_id)
        except SubscriptionPackage.DoesNotExist:
            pkg = packages.first()

        now = timezone.now()
        if billing_type == 'trial':
            trial_days = pkg.trial_days or 14
            sub_status    = Subscription.Status.TRIAL
            tenant_status = Tenant.Status.TRIAL
            billing_cycle = Subscription.BillingCycle.TRIAL
            end_date      = now + timezone.timedelta(days=trial_days)
            trial_ends_at = end_date
        elif billing_type == 'yearly':
            sub_status    = Subscription.Status.ACTIVE
            tenant_status = Tenant.Status.ACTIVE
            billing_cycle = Subscription.BillingCycle.YEARLY
            end_date      = now + timezone.timedelta(days=365)
            trial_ends_at = None
        else:  # monthly
            sub_status    = Subscription.Status.ACTIVE
            tenant_status = Tenant.Status.ACTIVE
            billing_cycle = Subscription.BillingCycle.MONTHLY
            end_date      = now + timezone.timedelta(days=30)
            trial_ends_at = None

        Subscription.objects.create(
            tenant=tenant,
            package=pkg,
            billing_cycle=billing_cycle,
            start_date=now,
            end_date=end_date,
            trial_ends_at=trial_ends_at,
            status=sub_status,
        )
        tenant.status = tenant_status
        tenant.save(update_fields=['status'])

        label = {'trial': '🆓 Free Trial', 'monthly': '📅 Monthly', 'yearly': '📅 Yearly'}.get(billing_type, billing_type.title())
        messages.success(
            request,
            f'✅ {label} subscription renewed for "{tenant.agency_name}" '
            f'until {end_date.strftime("%b %d, %Y")}.'
        )
        return redirect('superadmin:tenant_detail', slug=tenant.slug)

    base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000')
    site_url = getattr(settings, 'SITE_URL', f'http://{base_domain}')
    directory_url = f"{site_url}/a/{tenant.slug}/"
    subdomain_url = f"http://{tenant.slug}.{base_domain}/"

    context = {
        'tenant': tenant,
        'subscriptions': subscriptions,
        'payments': payments,
        'logs': logs,
        'domains': domains,
        'usage_stats': usage_stats,
        'directory_url': directory_url,
        'subdomain_url': subdomain_url,
        'trial_used': trial_used,
        'packages': packages,
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
        # Reset expiry notifications for the new cycle
        subscription.expiry_7day_notified = False
        subscription.expiry_3day_notified = False
        subscription.expiry_1day_notified = False
        subscription.expired_notified = False
        subscription.save()

    # Ensure Tenant status is active
    tenant = payment.tenant
    tenant.status = Tenant.Status.ACTIVE
    tenant.save()

    # 🔔 Send Confirmation Notification to Agency Admin
    from apps.notifications.services import notify_payment_approved
    notify_payment_approved(payment)

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

    # 🔔 Send Rejection Notification to Agency Admin
    from apps.notifications.services import notify_payment_rejected
    notify_payment_rejected(payment)

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


# ── SUPER ADMIN AGENCY NOTIFICATIONS & BROADCASTS ─────────────────────────────
@login_required
@user_passes_test(superadmin_required)
def superadmin_notifications(request):
    """Super Admin view for managing and inspecting agency notifications & broadcasts."""
    from apps.notifications.models import Notification

    type_filter = request.GET.get('type', '')
    target_filter = request.GET.get('tenant', '')

    try:
        notifications = Notification.objects.select_related('tenant').order_by('-created_at')

        if type_filter:
            notifications = notifications.filter(notification_type=type_filter)
        if target_filter:
            notifications = notifications.filter(tenant_id=target_filter)

        total_count = Notification.objects.count()
        maintenance_count = Notification.objects.filter(notification_type='maintenance').count()
        server_count = Notification.objects.filter(notification_type='server_update').count()
        work_count = Notification.objects.filter(notification_type='work_update').count()
        subscription_count = Notification.objects.filter(notification_type__in=['subscription', 'payment']).count()
        notification_items = list(notifications[:100])
    except Exception as e:
        notification_items = []
        total_count = 0
        maintenance_count = 0
        server_count = 0
        work_count = 0
        subscription_count = 0
        messages.warning(
            request,
            '⚠️ Notification tables need to be migrated. Please run "python manage.py migrate notifications" on your server.'
        )

    context = {
        'notifications': notification_items,
        'type_filter': type_filter,
        'target_filter': target_filter,
        'total_count': total_count,
        'maintenance_count': maintenance_count,
        'server_count': server_count,
        'work_count': work_count,
        'subscription_count': subscription_count,
    }
    return render(request, 'superadmin/notifications/list.html', context)


@login_required
@user_passes_test(superadmin_required)
def superadmin_notification_create(request):
    """Super Admin creates and sends notifications/broadcasts to agencies."""
    from apps.notifications.models import Notification
    from apps.notifications.services import broadcast_superadmin_notification

    tenants = Tenant.objects.order_by('agency_name')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()
        notification_type = request.POST.get('notification_type', 'maintenance')
        priority = request.POST.get('priority', 'normal')
        target_type = request.POST.get('target_type', 'all')
        target_tenant_id = request.POST.get('tenant_id') if target_type == 'specific' else None
        action_url = request.POST.get('action_url', '').strip()

        if not title or not message:
            messages.error(request, 'Please provide both title and message.')
            return redirect('superadmin:notification_create')

        count = broadcast_superadmin_notification(
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            target_tenant_id=target_tenant_id
        )

        messages.success(request, f'📢 Notification dispatched successfully to {count} agency account(s)!')
        return redirect('superadmin:notifications')

    context = {
        'tenants': tenants,
        'notification_types': Notification.NotificationType.choices,
        'priorities': Notification.Priority.choices,
    }
    return render(request, 'superadmin/notifications/create.html', context)


@login_required
@user_passes_test(superadmin_required)
def superadmin_notification_delete(request, uid):
    """Delete a sent notification record."""
    from apps.notifications.models import Notification
    notification = get_object_or_404(Notification, uid=uid)
    notification.delete()
    messages.info(request, 'Notification deleted.')
    return redirect('superadmin:notifications')


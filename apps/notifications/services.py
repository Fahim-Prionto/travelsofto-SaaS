"""
apps/notifications/services.py

Helper services to dispatch and manage SaaS agency notifications.
"""
import logging
from django.utils import timezone
from apps.notifications.models import Notification
from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


def create_agency_notification(
    tenant,
    notification_type,
    title,
    message,
    priority='normal',
    action_url='',
    recipient_email='',
    is_broadcast=False
):
    """Create a single notification targeted to an agency."""
    try:
        if not recipient_email and tenant:
            recipient_email = getattr(tenant, 'email', '') or ''
            if not recipient_email and hasattr(tenant, 'owner') and tenant.owner:
                recipient_email = tenant.owner.email or ''

        return Notification.objects.create(
            tenant=tenant,
            recipient_email=recipient_email,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            action_url=action_url,
            is_broadcast=is_broadcast,
        )
    except Exception as e:
        logger.error(f"Error creating agency notification for {tenant}: {e}")
        return None


def broadcast_superadmin_notification(
    notification_type,
    title,
    message,
    priority='normal',
    action_url='',
    target_tenant_id=None
):
    """
    Super Admin sends a maintenance, server update, work update, or general announcement.
    If target_tenant_id is provided, sends to only that tenant.
    Otherwise broadcasts to all active agencies.
    """
    if target_tenant_id:
        try:
            tenant = Tenant.objects.get(id=target_tenant_id)
            create_agency_notification(
                tenant=tenant,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                action_url=action_url,
                is_broadcast=False
            )
            return 1
        except Tenant.DoesNotExist:
            return 0

    # Broadcast to all active agencies
    active_tenants = Tenant.objects.all()
    notifications = []
    for tenant in active_tenants:
        recipient_email = getattr(tenant, 'email', '') or ''
        notifications.append(
            Notification(
                tenant=tenant,
                recipient_email=recipient_email,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                action_url=action_url,
                is_broadcast=True
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)
    return len(notifications)


def notify_payment_approved(payment):
    """Dispatch notification when Super Admin approves subscription payment."""
    tenant = payment.tenant
    subscription = payment.subscription
    pkg_name = payment.package.name if payment.package else 'SaaS Plan'
    end_date_str = subscription.end_date.strftime('%B %d, %Y') if subscription and subscription.end_date else 'Active'

    title = f"🎉 Payment Approved & Subscription Confirmed"
    message = (
        f"Great news! Your payment of ৳{payment.amount} for the {pkg_name} plan has been "
        f"verified and approved by the Super Admin. Your agency subscription is now active until {end_date_str}. "
        f"All modules and limits have been updated."
    )
    return create_agency_notification(
        tenant=tenant,
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.HIGH,
        title=title,
        message=message,
        action_url='/admin-panel/subscription/my-plan/'
    )


def notify_payment_rejected(payment):
    """Dispatch notification when Super Admin rejects a payment."""
    tenant = payment.tenant
    pkg_name = payment.package.name if payment.package else 'SaaS Plan'
    title = f"⚠️ Subscription Payment Rejected"
    message = (
        f"Your payment submission for {pkg_name} (Transaction ID: {payment.transaction_id}) "
        f"could not be verified by the Super Admin. Please check your transaction details, "
        f"contact support, or resubmit your payment."
    )
    return create_agency_notification(
        tenant=tenant,
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.URGENT,
        title=title,
        message=message,
        action_url='/admin-panel/subscription/checkout/'
    )


def notify_subscription_renewal_submitted(payment):
    """Dispatch notification when an agency submits subscription renewal payment."""
    tenant = payment.tenant
    pkg_name = payment.package.name if payment.package else 'SaaS Plan'
    title = f"🔄 Subscription Renewal Submitted"
    message = (
        f"Your renewal payment submission of ৳{payment.amount} for {pkg_name} "
        f"(Trx ID: {payment.transaction_id}) has been recorded. Our team will verify and activate "
        f"your subscription shortly."
    )
    return create_agency_notification(
        tenant=tenant,
        notification_type=Notification.NotificationType.SUBSCRIPTION,
        priority=Notification.Priority.NORMAL,
        title=title,
        message=message,
        action_url='/admin-panel/subscription/pending/'
    )


def check_and_notify_subscription_time(tenant, subscription):
    """
    Checks subscription expiration date and automatically generates warnings:
      - 7 days remaining
      - 3 days remaining (Urgent)
      - 1 day remaining (Urgent)
      - Expired alert
    """
    if not subscription or not subscription.end_date:
        return

    now = timezone.now()
    delta = subscription.end_date - now
    days_remaining = delta.days
    pkg_name = subscription.package.name if subscription.package else 'Subscription'
    end_date_str = subscription.end_date.strftime('%B %d, %Y')

    # 1. Expired Notification
    if now >= subscription.end_date:
        if not getattr(subscription, 'expired_notified', False):
            create_agency_notification(
                tenant=tenant,
                notification_type=Notification.NotificationType.SUBSCRIPTION,
                priority=Notification.Priority.URGENT,
                title=f"🛑 Subscription Expired",
                message=(
                    f"Your subscription for {pkg_name} expired on {end_date_str}. "
                    f"To prevent interruption to your website and agency operations, "
                    f"please renew your plan immediately."
                ),
                action_url='/admin-panel/subscription/checkout/'
            )
            subscription.expired_notified = True
            subscription.save(update_fields=['expired_notified'])
        return

    # 2. 1-day alert
    if days_remaining <= 1 and not getattr(subscription, 'expiry_1day_notified', False):
        create_agency_notification(
            tenant=tenant,
            notification_type=Notification.NotificationType.SUBSCRIPTION,
            priority=Notification.Priority.URGENT,
            title=f"🚨 Final Notice: Subscription Expires in 24 Hours",
            message=(
                f"Your {pkg_name} subscription will expire tomorrow on {end_date_str}. "
                f"Please renew now to keep your bookings, customer access, and custom domain active."
            ),
            action_url='/admin-panel/subscription/checkout/'
        )
        subscription.expiry_1day_notified = True
        subscription.save(update_fields=['expiry_1day_notified'])
        return

    # 3. 3-day alert
    if days_remaining <= 3 and not getattr(subscription, 'expiry_3day_notified', False):
        create_agency_notification(
            tenant=tenant,
            notification_type=Notification.NotificationType.SUBSCRIPTION,
            priority=Notification.Priority.HIGH,
            title=f"⚠️ Subscription Expiring in {days_remaining} Days",
            message=(
                f"Your agency subscription for {pkg_name} will expire on {end_date_str} "
                f"({days_remaining} days remaining). Please renew your subscription to ensure smooth service."
            ),
            action_url='/admin-panel/subscription/checkout/'
        )
        subscription.expiry_3day_notified = True
        subscription.save(update_fields=['expiry_3day_notified'])
        return

    # 4. 7-day alert
    if days_remaining <= 7 and not getattr(subscription, 'expiry_7day_notified', False):
        create_agency_notification(
            tenant=tenant,
            notification_type=Notification.NotificationType.SUBSCRIPTION,
            priority=Notification.Priority.NORMAL,
            title=f"⏳ Subscription Expiring Soon (7 Days Left)",
            message=(
                f"Notice: Your {pkg_name} subscription will expire on {end_date_str}. "
                f"You have 7 days remaining. You can renew at any time from your billing overview."
            ),
            action_url='/admin-panel/subscription/my-plan/'
        )
        subscription.expiry_7day_notified = True
        subscription.save(update_fields=['expiry_7day_notified'])
        return


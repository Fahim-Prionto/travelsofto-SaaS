"""
apps/notifications/context_processors.py

Provides real-time agency notification count and dropdown items to all admin panel templates.
"""
from apps.notifications.models import Notification
from apps.tenants.models import Tenant


def agency_notifications(request):
    """Context processor providing unread notifications for the logged in agency."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        return {}

    try:
        tenant = Tenant.objects.filter(slug=tenant_id).first()
        if not tenant:
            return {}

        # Fetch unread count & recent notifications for this agency
        qs = Notification.objects.filter(tenant=tenant)
        unread_count = qs.filter(is_read=False).count()
        recent_notifications = list(qs.order_by('-created_at')[:6])

        # Urgent notification banner (e.g. maintenance schedule or server update)
        urgent_announcement = qs.filter(
            is_read=False,
            priority__in=['high', 'urgent']
        ).first()

        return {
            'unread_notifications_count': unread_count,
            'recent_agency_notifications': recent_notifications,
            'urgent_agency_announcement': urgent_announcement,
        }
    except Exception:
        return {
            'unread_notifications_count': 0,
            'recent_agency_notifications': [],
            'urgent_agency_announcement': None,
        }


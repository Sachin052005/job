def notifications_context(request):
    if not request.user.is_authenticated:
        return {}
    notifications = request.user.notifications.select_related("job", "company", "application")
    return {
        "unread_notification_count": notifications.filter(is_read=False).count(),
        "recent_notifications": list(notifications[:6]),
    }

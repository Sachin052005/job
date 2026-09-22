from adminpanel.mixins import AdminDeleteView, AdminDetailView, AdminListView, BulkAction, FilterSpec
from core.constants import NOTIFICATION_TYPE_CHOICES
from notifications.models import Notification


class NotificationListView(AdminListView):
    model = Notification
    page_title = "Notifications"
    search_fields = ["recipient__username", "title", "message"]
    columns = [
        ("Recipient", "recipient.username"),
        ("Type", "get_notification_type_display"),
        ("Title", "title"),
        ("Read", "is_read"),
        ("Created", "created_at"),
    ]
    filter_specs = [
        FilterSpec("notification_type", "Type", NOTIFICATION_TYPE_CHOICES),
        FilterSpec("is_read", "Read status", [("1", "Read"), ("0", "Unread")]),
    ]
    row_view_url_name = "adminpanel:notification_detail"
    row_delete_url_name = "adminpanel:notification_delete"
    ordering = ["-created_at"]
    select_related_fields = ["recipient"]
    bulk_actions = [
        BulkAction("mark_read", "Mark read"),
        BulkAction("mark_unread", "Mark unread"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_mark_read(self, queryset):
        queryset.update(is_read=True)

    def bulk_mark_unread(self, queryset):
        queryset.update(is_read=False)

    def bulk_delete(self, queryset):
        queryset.delete()


class NotificationDetailView(AdminDetailView):
    model = Notification
    page_title = "Notification"
    delete_url_name = "adminpanel:notification_delete"
    list_url_name = "adminpanel:notification_list"
    detail_fields = [
        ("Recipient", "recipient.username"),
        ("Type", "get_notification_type_display"),
        ("Title", "title"),
        ("Message", "message"),
        ("Read", "is_read"),
        ("Job", "job.title"),
        ("Application", "application"),
        ("Company", "company.name"),
        ("Created", "created_at"),
    ]


class NotificationDeleteView(AdminDeleteView):
    model = Notification
    page_title = "Delete Notification"
    list_url_name = "adminpanel:notification_list"

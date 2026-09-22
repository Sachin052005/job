from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "notification_type", "title", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["recipient__username", "title", "message"]
    autocomplete_fields = ["recipient", "job", "application", "company", "actor"]
    readonly_fields = ["created_at"]

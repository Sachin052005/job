from django.contrib import admin

from applications.models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["applicant", "job", "status", "applied_at"]
    list_filter = ["status"]
    search_fields = ["applicant__username", "job__title"]
    autocomplete_fields = ["applicant", "job"]
    readonly_fields = ["applied_at", "updated_at"]

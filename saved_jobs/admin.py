from django.contrib import admin

from saved_jobs.models import SavedJob


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ["user", "job", "saved_at"]
    search_fields = ["user__username", "job__title"]

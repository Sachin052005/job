from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "location", "experience_years", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email", "location", "skills"]
    autocomplete_fields = ["user"]

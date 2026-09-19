from django.contrib import admin

from companies.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "industry", "location", "created_at"]
    list_filter = ["industry"]
    search_fields = ["name", "owner__username", "location"]
    prepopulated_fields = {"slug": ("name",)}

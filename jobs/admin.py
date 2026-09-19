from django.contrib import admin

from jobs.models import Category, Job


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "employer", "employment_type", "status", "location", "created_at"]
    list_filter = ["status", "employment_type", "category"]
    search_fields = ["title", "location", "skills", "company__name"]
    autocomplete_fields = ["employer", "company", "category"]
    readonly_fields = ["views_count", "published_at", "created_at", "updated_at"]
    ordering = ["-created_at"]

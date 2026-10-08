from django.contrib import admin

from jobs.models import Category, Job, JobDomain, JobSubdomain, JobView


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


class JobSubdomainInline(admin.TabularInline):
    model = JobSubdomain
    extra = 0
    prepopulated_fields = {"slug": ("name",)}


@admin.register(JobDomain)
class JobDomainAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "display_order"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [JobSubdomainInline]


@admin.register(JobSubdomain)
class JobSubdomainAdmin(admin.ModelAdmin):
    list_display = ["name", "domain", "slug", "is_active", "display_order"]
    list_filter = ["domain", "is_active"]
    search_fields = ["name"]
    autocomplete_fields = ["domain"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "employer", "employment_type", "application_method", "status", "location", "created_at"]
    list_filter = ["status", "employment_type", "application_method", "work_mode", "domain", "category"]
    search_fields = ["title", "location", "skills", "company__name"]
    autocomplete_fields = ["employer", "company", "category", "domain", "subdomain"]
    readonly_fields = ["views_count", "published_at", "created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(JobView)
class JobViewAdmin(admin.ModelAdmin):
    list_display = ["job", "viewer", "session_key", "viewed_at"]
    list_filter = ["viewed_at"]
    search_fields = ["job__title", "viewer__username"]
    autocomplete_fields = ["job", "viewer"]
    readonly_fields = ["job", "viewer", "session_key", "viewed_at"]

    def has_add_permission(self, request):
        return False

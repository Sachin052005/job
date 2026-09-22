from django.contrib import admin

from companies.models import (
    Company,
    CompanyFollow,
    CompanyOffice,
    CompanyProductService,
    CompanyReview,
    CompanySalary,
)


class CompanyOfficeInline(admin.TabularInline):
    model = CompanyOffice
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "industry", "location", "verification_status", "created_at"]
    list_filter = ["industry", "company_type", "verification_status"]
    search_fields = ["name", "owner__username", "location"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CompanyOfficeInline]


@admin.register(CompanyFollow)
class CompanyFollowAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "followed_at"]
    search_fields = ["user__username", "company__name"]


@admin.register(CompanyOffice)
class CompanyOfficeAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "office_type", "city", "is_headquarters"]
    list_filter = ["office_type", "is_headquarters"]
    search_fields = ["company__name", "city", "name"]


@admin.register(CompanySalary)
class CompanySalaryAdmin(admin.ModelAdmin):
    list_display = ["company", "role", "salary_range", "experience_level", "employment_type"]
    list_filter = ["experience_level", "employment_type"]
    search_fields = ["company__name", "role"]


@admin.register(CompanyProductService)
class CompanyProductServiceAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "item_type", "order"]
    list_filter = ["item_type"]
    search_fields = ["company__name", "name"]


@admin.register(CompanyReview)
class CompanyReviewAdmin(admin.ModelAdmin):
    list_display = ["company", "applicant", "rating", "is_active", "created_at"]
    list_filter = ["rating", "is_active"]
    search_fields = ["company__name", "applicant__username"]
    readonly_fields = ["company", "applicant", "application", "rating", "content", "image", "created_at", "updated_at"]

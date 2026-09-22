from django.contrib import admin

from applications.models import Application, ApplicationStatusHistory, ScreeningAnswer


class ScreeningAnswerInline(admin.TabularInline):
    model = ScreeningAnswer
    extra = 0


class ApplicationStatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    readonly_fields = ["old_status", "new_status", "changed_by", "changed_at"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["applicant", "job", "status", "applied_via", "match_percentage", "applied_at"]
    list_filter = ["status", "applied_via"]
    search_fields = ["applicant__username", "job__title", "first_name", "last_name", "email"]
    autocomplete_fields = ["applicant", "job"]
    readonly_fields = [
        "applied_at",
        "updated_at",
        "match_percentage",
        "matched_skills",
        "unmatched_skills",
        "student_skills_snapshot",
        "job_skills_snapshot",
    ]
    inlines = [ScreeningAnswerInline, ApplicationStatusHistoryInline]

from django.contrib import admin

from applications.models import Application, ApplicationStatusHistory, Interview, RecruiterNote


class ApplicationStatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    readonly_fields = ["old_status", "new_status", "changed_by", "note", "changed_at"]


class InterviewInline(admin.TabularInline):
    model = Interview
    extra = 0


class RecruiterNoteInline(admin.TabularInline):
    model = RecruiterNote
    extra = 0
    readonly_fields = ["author", "created_at"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["applicant", "job", "status", "applied_via", "match_percentage", "ats_status", "ats_score", "applied_at"]
    list_filter = ["status", "applied_via", "ats_status"]
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
        "ats_status",
        "ats_score",
        "ats_breakdown",
        "ats_error",
        "ats_processed_at",
    ]
    inlines = [ApplicationStatusHistoryInline, InterviewInline, RecruiterNoteInline]


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ["application", "interview_type", "scheduled_at", "interviewer", "result"]
    list_filter = ["interview_type", "result"]
    autocomplete_fields = ["application", "interviewer", "created_by"]
    search_fields = ["application__applicant__username", "application__job__title"]


@admin.register(RecruiterNote)
class RecruiterNoteAdmin(admin.ModelAdmin):
    list_display = ["application", "author", "created_at"]
    autocomplete_fields = ["application", "author"]
    search_fields = ["application__applicant__username", "text"]
    readonly_fields = ["created_at", "updated_at"]

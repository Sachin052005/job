from django.contrib import admin

from resumes.models import Resume, ResumeJobMatch, ResumeScan


class ResumeScanInline(admin.TabularInline):
    model = ResumeScan
    extra = 0
    readonly_fields = ["score", "score_breakdown", "extracted_data", "issues", "recommendations", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ["title", "student", "is_primary", "created_at", "updated_at"]
    list_filter = ["is_primary", "created_at"]
    search_fields = ["title", "student__username"]
    autocomplete_fields = ["student"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ResumeScanInline]


@admin.register(ResumeJobMatch)
class ResumeJobMatchAdmin(admin.ModelAdmin):
    list_display = ["resume", "job", "compatibility_score", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["resume__title", "resume__student__username", "job__title"]
    autocomplete_fields = ["resume", "job"]
    readonly_fields = [
        "resume",
        "job",
        "job_description_text",
        "compatibility_score",
        "matched_skills",
        "missing_skills",
        "analysis",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

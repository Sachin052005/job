from django.contrib import admin

from resumes.models import ATSIssue, Resume, ResumeJobMatch, ResumeScan


class ATSIssueInline(admin.TabularInline):
    model = ATSIssue
    extra = 0
    readonly_fields = ["category", "severity", "section", "text", "message", "suggestion", "created_at"]
    fields = ["category", "severity", "status", "message", "text", "suggestion", "created_at"]


class ResumeScanInline(admin.TabularInline):
    model = ResumeScan
    extra = 0
    readonly_fields = ["score", "score_breakdown", "extracted_data", "issues", "recommendations", "analyzer_version", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ["title", "student", "is_primary", "parse_status", "created_at", "updated_at"]
    list_filter = ["is_primary", "parse_status", "created_at"]
    search_fields = ["title", "student__username"]
    autocomplete_fields = ["student"]
    readonly_fields = ["created_at", "updated_at", "file_hash", "parsed_at", "parser_version"]
    inlines = [ResumeScanInline]


@admin.register(ResumeScan)
class ResumeScanAdmin(admin.ModelAdmin):
    list_display = ["resume", "score", "analyzer_version", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["resume__title", "resume__student__username"]
    autocomplete_fields = ["resume"]
    readonly_fields = ["score", "score_breakdown", "extracted_data", "issues", "recommendations", "analyzer_version", "created_at"]
    inlines = [ATSIssueInline]

    def has_add_permission(self, request):
        return False


@admin.register(ATSIssue)
class ATSIssueAdmin(admin.ModelAdmin):
    list_display = ["resume", "category", "severity", "status", "message", "created_at"]
    list_filter = ["severity", "status", "category"]
    search_fields = ["resume__title", "message"]
    autocomplete_fields = ["resume", "scan"]
    readonly_fields = ["created_at", "updated_at"]


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

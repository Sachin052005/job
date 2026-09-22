from django.contrib import admin

from activity.models import StudentActivity, StudentProfileView, StudentSearchAppearance


@admin.register(StudentSearchAppearance)
class StudentSearchAppearanceAdmin(admin.ModelAdmin):
    list_display = ["student", "recruiter", "company", "search_query", "created_at"]
    list_filter = ["created_at", "company"]
    search_fields = ["student__username", "recruiter__username", "company__name", "search_query"]
    autocomplete_fields = ["student", "recruiter", "company"]
    readonly_fields = ["created_at"]

    def has_add_permission(self, request):
        return False


@admin.register(StudentProfileView)
class StudentProfileViewAdmin(admin.ModelAdmin):
    list_display = ["student", "recruiter", "company", "source", "viewed_at"]
    list_filter = ["source", "viewed_at", "company"]
    search_fields = ["student__username", "recruiter__username", "company__name"]
    autocomplete_fields = ["student", "recruiter", "company"]
    readonly_fields = ["viewed_at"]

    def has_add_permission(self, request):
        return False


@admin.register(StudentActivity)
class StudentActivityAdmin(admin.ModelAdmin):
    list_display = ["student", "event_type", "recruiter", "company", "job", "created_at"]
    list_filter = ["event_type", "created_at", "company"]
    search_fields = ["student__username", "recruiter__username", "company__name"]
    autocomplete_fields = ["student", "recruiter", "company", "application", "job"]
    readonly_fields = ["created_at"]

    def has_add_permission(self, request):
        return False

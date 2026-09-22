from django.contrib import admin

from accounts.models import (
    Accomplishment,
    CandidateSkill,
    CareerPreference,
    Education,
    Internship,
    JobAlert,
    Language,
    Profile,
    Project,
    RecruiterProfile,
    SocialAccount,
    UserSettings,
    WorkExperience,
)


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0


class WorkExperienceInline(admin.TabularInline):
    model = WorkExperience
    extra = 0


class CandidateSkillInline(admin.TabularInline):
    model = CandidateSkill
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "location", "experience_years", "completion_percent", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email", "location", "skills"]
    autocomplete_fields = ["user"]
    inlines = [EducationInline, WorkExperienceInline, CandidateSkillInline]


@admin.register(CareerPreference)
class CareerPreferenceAdmin(admin.ModelAdmin):
    list_display = ["profile", "job_search_status", "work_mode", "employment_type", "updated_at"]
    list_filter = ["job_search_status", "work_mode", "employment_type"]
    search_fields = ["profile__user__username"]


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ["profile", "degree", "institution", "start_year", "end_year"]
    search_fields = ["profile__user__username", "degree", "institution"]


@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display = ["profile", "designation", "company", "start_date", "end_date", "is_current"]
    list_filter = ["is_current"]
    search_fields = ["profile__user__username", "company", "designation"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["profile", "title", "start_date", "end_date"]
    search_fields = ["profile__user__username", "title"]


@admin.register(Internship)
class InternshipAdmin(admin.ModelAdmin):
    list_display = ["profile", "role", "company", "start_date", "end_date"]
    search_fields = ["profile__user__username", "company", "role"]


@admin.register(Accomplishment)
class AccomplishmentAdmin(admin.ModelAdmin):
    list_display = ["profile", "title", "category", "date"]
    list_filter = ["category"]
    search_fields = ["profile__user__username", "title"]


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["profile", "name", "proficiency"]
    list_filter = ["proficiency"]
    search_fields = ["profile__user__username", "name"]


@admin.register(CandidateSkill)
class CandidateSkillAdmin(admin.ModelAdmin):
    list_display = ["profile", "name", "proficiency", "is_primary", "years_experience"]
    list_filter = ["proficiency", "is_primary"]
    search_fields = ["profile__user__username", "name"]


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "theme", "profile_visibility", "updated_at"]
    list_filter = ["theme", "profile_visibility"]
    search_fields = ["user__username"]


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "provider", "provider_user_id", "created_at"]
    list_filter = ["provider"]
    search_fields = ["user__username", "provider_user_id", "email"]


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "job_title", "verification_status", "updated_at"]
    list_filter = ["specialization", "verification_status"]
    search_fields = ["user__username", "job_title", "company__name"]
    autocomplete_fields = ["user", "company"]


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "frequency", "is_active", "created_at"]
    list_filter = ["frequency", "is_active"]
    search_fields = ["name", "user__username", "keywords"]

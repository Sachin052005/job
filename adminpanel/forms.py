"""Forms unique to the manual admin panel.

Everything that already has a usable ModelForm elsewhere in the project
(EducationForm, CompanyOfficeForm, ApplicationStatusForm, JobAlertForm, ...)
is imported and reused directly from its owning app in adminpanel/views/ -
this module only defines what doesn't already exist, per spec section 32/45
("do not duplicate validation logic" / "do not duplicate business logic").
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from accounts.models import Profile, RecruiterProfile, SocialAccount, UserSettings
from companies.models import Company, CompanyReview
from jobs.forms import JobForm
from jobs.models import Category

User = get_user_model()

_CHECKBOX = forms.CheckboxInput(attrs={"class": "form-check-input"})


class AdminUserCreateForm(UserCreationForm):
    """Create a User from the admin panel - staff/superuser/active flags are
    plain form fields here (unlike public RegisterForm), matching spec
    section 16. Password always goes through set_password() via UserCreationForm."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "is_superuser", "password1", "password2",
        ]
        widgets = {"is_active": _CHECKBOX, "is_staff": _CHECKBOX, "is_superuser": _CHECKBOX}

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class AdminUserEditForm(forms.ModelForm):
    """Edit an existing User's account fields. Never exposes/edits the
    password hash (spec sections 16/48) - use the separate password-reset
    action, which calls set_password()."""

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active", "is_staff", "is_superuser"]
        widgets = {"is_active": _CHECKBOX, "is_staff": _CHECKBOX, "is_superuser": _CHECKBOX}


class AdminProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "role", "phone", "location", "headline", "summary", "skills",
            "experience_years", "linkedin_url", "github_url", "portfolio_url",
        ]
        widgets = {"summary": forms.Textarea(attrs={"rows": 4})}


class AdminUserSettingsForm(forms.ModelForm):
    """Single combined settings form for admin use - the candidate-facing UI
    intentionally splits this into Theme/Notifications/Privacy forms
    (accounts/forms.py), but one admin screen covering all of UserSettings
    is more useful for support/moderation."""

    class Meta:
        model = UserSettings
        fields = [
            "theme",
            "notify_job_alerts", "notify_application_updates", "notify_recruiter_updates",
            "notify_company_updates", "notify_interview_reminders", "notify_system",
            "profile_visibility", "recruiters_can_view_profile", "recruiters_can_download_resume",
            "recruiters_can_contact", "show_in_recruiter_search",
        ]
        widgets = {
            field: _CHECKBOX
            for field in [
                "notify_job_alerts", "notify_application_updates", "notify_recruiter_updates",
                "notify_company_updates", "notify_interview_reminders", "notify_system",
                "recruiters_can_view_profile", "recruiters_can_download_resume",
                "recruiters_can_contact", "show_in_recruiter_search",
            ]
        }


class SocialAccountForm(forms.ModelForm):
    class Meta:
        model = SocialAccount
        fields = ["provider", "provider_user_id", "email"]


class AdminRecruiterProfileForm(forms.ModelForm):
    """Superset of accounts.forms.RecruiterProfileForm - adds `company` and
    `verification_status`, which only an admin (not the recruiter) may set."""

    class Meta:
        model = RecruiterProfile
        fields = [
            "company", "job_title", "department", "professional_experience_years",
            "recruitment_experience_years", "specialization", "roles_hiring_for",
            "hiring_domains", "candidate_experience_pref", "hiring_locations",
            "salary_range_min", "salary_range_max", "employment_types_hiring",
            "remote_hiring", "freshers_hiring", "urgent_hiring", "designation",
            "official_company_email", "employee_id", "recruiter_role", "verification_status",
        ]
        widgets = {
            field: _CHECKBOX for field in ["remote_hiring", "freshers_hiring", "urgent_hiring"]
        }


class AdminCompanyForm(forms.ModelForm):
    """Full-field company form for admin use - the recruiter-facing
    CompanyForm/CompanyContentForm (companies/forms.py) intentionally split
    this into a smaller onboarding form plus a content-editing form; admin
    needs everything (including owner + verification) on one screen."""

    class Meta:
        model = Company
        fields = [
            "owner", "name", "legal_name", "description", "industry", "sub_industry",
            "company_type", "website", "location", "founded_year", "size", "logo", "cover_image",
            "mission", "vision", "official_email", "official_phone", "products", "services_offered",
            "technologies", "culture", "work_environment", "benefits", "official_domain",
            "verification_status",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "mission": forms.Textarea(attrs={"rows": 3}),
            "vision": forms.Textarea(attrs={"rows": 3}),
            "products": forms.Textarea(attrs={"rows": 3}),
            "services_offered": forms.Textarea(attrs={"rows": 3}),
            "culture": forms.Textarea(attrs={"rows": 3}),
            "work_environment": forms.Textarea(attrs={"rows": 3}),
            "benefits": forms.Textarea(attrs={"rows": 3}),
        }


class CompanyReviewModerationForm(forms.ModelForm):
    """Moderation only - the student's rating/content is never edited by
    admin, only shown/hidden (spec section 21)."""

    class Meta:
        model = CompanyReview
        fields = ["is_active"]
        widgets = {"is_active": _CHECKBOX}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class AdminJobForm(JobForm):
    """JobForm already handles badges + screening-question sync (spec
    section 45: reuse, don't duplicate) - this only adds employer/company,
    which the recruiter-facing form fixes to request.user/request.user.company
    but an admin must be able to reassign."""

    class Meta(JobForm.Meta):
        fields = ["employer", "company"] + list(JobForm.Meta.fields)

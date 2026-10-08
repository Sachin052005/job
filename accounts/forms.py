from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

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
    UserSettings,
    WorkExperience,
)
from core.constants import ROLE_CHOICES

User = get_user_model()

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"})


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
            profile = user.profile
            profile.role = self.cleaned_data["role"]
            profile.save()
        return user


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileForm(forms.ModelForm):
    # website_url intentionally excluded from the candidate-facing form - the
    # column stays on the model (see accounts/models.py) but candidates no
    # longer see/edit a generic "Website" field. Use Project.project_url or
    # Project.github_url instead.
    class Meta:
        model = Profile
        fields = [
            "phone",
            "location",
            "headline",
            "summary",
            "skills",
            "experience_years",
            "photo",
            "resume",
            "linkedin_url",
            "github_url",
            "portfolio_url",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "linkedin_url": forms.URLInput(attrs={"placeholder": "https://www.linkedin.com/in/yourname"}),
            "github_url": forms.URLInput(attrs={"placeholder": "https://github.com/yourname"}),
            "portfolio_url": forms.URLInput(attrs={"placeholder": "https://yourportfolio.com"}),
        }


class CareerPreferenceForm(forms.ModelForm):
    class Meta:
        model = CareerPreference
        fields = [
            "preferred_job_title",
            "preferred_role",
            "preferred_industry",
            "preferred_department",
            "preferred_location",
            "work_mode",
            "employment_type",
            "experience_level",
            "expected_salary",
            "notice_period",
            "willing_to_relocate",
            "preferred_shift",
            "preferred_company_type",
            "job_search_status",
        ]


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = [
            "level",
            "degree",
            "specialization",
            "institution",
            "university",
            "start_year",
            "end_year",
            "grade",
        ]


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = [
            "company",
            "designation",
            "employment_type",
            "location",
            "start_date",
            "end_date",
            "is_current",
            "description",
            "skills_used",
        ]
        widgets = {
            "start_date": _DATE_WIDGET,
            "end_date": _DATE_WIDGET,
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_current = cleaned_data.get("is_current")
        end_date = cleaned_data.get("end_date")
        if is_current:
            cleaned_data["end_date"] = None
        elif not end_date:
            self.add_error("end_date", "End date is required unless this is your current job.")
        return cleaned_data


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "title",
            "description",
            "technologies",
            "role",
            "start_date",
            "end_date",
            "project_url",
            "github_url",
            "team_size",
            "achievements",
        ]
        widgets = {
            "start_date": _DATE_WIDGET,
            "end_date": _DATE_WIDGET,
            "description": forms.Textarea(attrs={"rows": 3}),
            "achievements": forms.Textarea(attrs={"rows": 2}),
        }


class InternshipForm(forms.ModelForm):
    class Meta:
        model = Internship
        fields = [
            "company",
            "role",
            "location",
            "start_date",
            "end_date",
            "description",
            "skills",
            "certificate",
        ]
        widgets = {
            "start_date": _DATE_WIDGET,
            "end_date": _DATE_WIDGET,
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class AccomplishmentForm(forms.ModelForm):
    class Meta:
        model = Accomplishment
        fields = ["category", "title", "issuer", "date", "url", "description"]
        widgets = {
            "date": _DATE_WIDGET,
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class LanguageForm(forms.ModelForm):
    class Meta:
        model = Language
        fields = ["name", "proficiency"]


class CandidateSkillForm(forms.ModelForm):
    class Meta:
        model = CandidateSkill
        fields = ["name", "proficiency", "years_experience", "is_primary"]


class JobAlertForm(forms.ModelForm):
    class Meta:
        model = JobAlert
        fields = [
            "name", "keywords", "domain", "location", "experience_max",
            "salary_min", "employment_type", "work_mode", "frequency", "is_active",
        ]
        widgets = {"is_active": forms.CheckboxInput(attrs={"class": "form-check-input"})}


class UserSettingsThemeForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["theme"]
        widgets = {"theme": forms.RadioSelect(attrs={"class": "js-theme-radio"})}


_SWITCH_ATTRS = {"class": "form-check-input"}


class UserSettingsNotificationsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            "notify_job_alerts", "notify_application_updates", "notify_recruiter_updates",
            "notify_company_updates", "notify_interview_reminders", "notify_system",
        ]
        widgets = {field: forms.CheckboxInput(attrs=_SWITCH_ATTRS) for field in fields}


class UserSettingsPrivacyForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            "profile_visibility", "recruiters_can_view_profile", "recruiters_can_download_resume",
            "recruiters_can_contact", "show_in_recruiter_search",
        ]
        widgets = {
            "profile_visibility": forms.RadioSelect,
            "recruiters_can_view_profile": forms.CheckboxInput(attrs=_SWITCH_ATTRS),
            "recruiters_can_download_resume": forms.CheckboxInput(attrs=_SWITCH_ATTRS),
            "recruiters_can_contact": forms.CheckboxInput(attrs=_SWITCH_ATTRS),
            "show_in_recruiter_search": forms.CheckboxInput(attrs=_SWITCH_ATTRS),
        }



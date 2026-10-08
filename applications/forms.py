from django import forms
from django.db.models import Q

from applications.models import Application, Interview, RecruiterNote

_REQUIRED_APPLY_FIELDS = ["first_name", "last_name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url"]

_SHARED_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "phone",
    "location",
    "current_company",
    "current_title",
    "experience_years",
    "education_summary",
    "skills",
    "resume",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "cover_letter",
]

_SHARED_WIDGETS = {
    "cover_letter": forms.Textarea(attrs={"rows": 5, "placeholder": "Why are you a great fit for this role?"}),
    "education_summary": forms.TextInput(attrs={"placeholder": "e.g. B.Tech Computer Science, 2024, 8.2 CGPA"}),
    "linkedin_url": forms.URLInput(attrs={"placeholder": "https://www.linkedin.com/in/yourname"}),
    "github_url": forms.URLInput(attrs={"placeholder": "https://github.com/yourname"}),
    "portfolio_url": forms.URLInput(attrs={"placeholder": "https://yourportfolio.com"}),
}


class ApplicationForm(forms.ModelForm):
    """Full manual "Apply" form (spec section 15) - LinkedIn/GitHub/Portfolio must exist and are required."""

    class Meta:
        model = Application
        fields = _SHARED_FIELDS
        widgets = _SHARED_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in _REQUIRED_APPLY_FIELDS:
            self.fields[field].required = True


class ApplicationStatusForm(forms.ModelForm):
    note = forms.CharField(
        required=False, max_length=300, label="Note (optional)",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Strong Django background, schedule technical round"}),
    )

    class Meta:
        model = Application
        fields = ["status"]


class RecruiterNoteForm(forms.ModelForm):
    class Meta:
        model = RecruiterNote
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Private note - only your company's recruiters can see this"}),
        }


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["interview_type", "scheduled_at", "location", "meeting_link", "interviewer", "notes"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if company is not None:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            self.fields["interviewer"].queryset = User.objects.filter(
                Q(pk=company.owner_id) | Q(recruiter_profile__company=company)
            ).distinct()


class InterviewResultForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["result", "feedback"]
        widgets = {"feedback": forms.Textarea(attrs={"rows": 3})}

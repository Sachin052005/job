from django import forms

from applications.models import Application, ScreeningAnswer

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
    class Meta:
        model = Application
        fields = ["status"]


class ScreeningAnswerForm(forms.Form):
    """Dynamically built from a job's ScreeningQuestion set."""

    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions or [])
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.CharField(
                label=question.question,
                required=question.is_required,
                widget=forms.Textarea(attrs={"rows": 2}),
            )

    def save(self, application):
        for question in self.questions:
            value = self.cleaned_data.get(f"question_{question.pk}", "").strip()
            if value:
                ScreeningAnswer.objects.update_or_create(
                    application=application, question=question, defaults={"answer_text": value}
                )

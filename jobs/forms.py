from django import forms

from core.constants import EMPLOYMENT_TYPE_CHOICES, JOB_BADGE_CHOICES
from jobs.models import Category, Job


class JobForm(forms.ModelForm):
    badges = forms.MultipleChoiceField(
        choices=JOB_BADGE_CHOICES, required=False, widget=forms.CheckboxSelectMultiple
    )
    screening_questions = forms.CharField(
        required=False,
        label="Screening Questions",
        help_text="One question per line. All are required unless prefixed with (optional).",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "category",
            "location",
            "work_mode",
            "description",
            "responsibilities",
            "skills",
            "employment_type",
            "experience_min",
            "experience_max",
            "education_required",
            "salary_min",
            "salary_max",
            "benefits",
            "highlights",
            "badges",
            "application_method",
            "status",
            "application_deadline",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "responsibilities": forms.Textarea(attrs={"rows": 4}),
            "benefits": forms.Textarea(attrs={"rows": 3}),
            "highlights": forms.Textarea(attrs={"rows": 3}),
            "application_deadline": forms.DateInput(attrs={"type": "date"}),
            "application_method": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["badges"].initial = self.instance.badges_list()
            self.fields["screening_questions"].initial = "\n".join(
                q.question for q in self.instance.screening_questions.all()
            )

    def clean(self):
        cleaned_data = super().clean()
        exp_min = cleaned_data.get("experience_min")
        exp_max = cleaned_data.get("experience_max")
        if exp_min is not None and exp_max is not None and exp_min > exp_max:
            raise forms.ValidationError("Minimum experience cannot be greater than maximum experience.")

        sal_min = cleaned_data.get("salary_min")
        sal_max = cleaned_data.get("salary_max")
        if sal_min is not None and sal_max is not None and sal_min > sal_max:
            raise forms.ValidationError("Minimum salary cannot be greater than maximum salary.")
        return cleaned_data

    def save(self, commit=True):
        job = super().save(commit=False)
        job.badges = ",".join(self.cleaned_data.get("badges", []))
        if commit:
            job.save()
            self.save_screening_questions(job)
        return job

    def save_screening_questions(self, job):
        from jobs.models import ScreeningQuestion

        lines = [line.strip() for line in self.cleaned_data.get("screening_questions", "").splitlines() if line.strip()]
        job.screening_questions.all().delete()
        for order, line in enumerate(lines):
            is_required = not line.lower().startswith("(optional)")
            text = line[len("(optional)"):].strip() if not is_required else line
            ScreeningQuestion.objects.create(job=job, question=text, is_required=is_required, order=order)


class JobSearchForm(forms.Form):
    keyword = forms.CharField(required=False, label="", widget=forms.TextInput(
        attrs={"placeholder": "Job title, skills, or company", "class": "form-control"}
    ))
    location = forms.CharField(required=False, label="", widget=forms.TextInput(
        attrs={"placeholder": "Location", "class": "form-control"}
    ))
    category = forms.ModelChoiceField(
        required=False, queryset=Category.objects.all(), to_field_name="slug", empty_label="All Categories",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    employment_type = forms.ChoiceField(
        required=False, choices=[("", "Any Employment Type")] + EMPLOYMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    experience = forms.IntegerField(
        required=False, min_value=0, label="Max experience (years)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Max exp"}),
    )
    salary_min = forms.IntegerField(required=False, min_value=0, label="Minimum salary")
    freshers_only = forms.BooleanField(required=False)
    remote_only = forms.BooleanField(required=False)
    urgent_only = forms.BooleanField(required=False)

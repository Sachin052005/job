from django import forms

from core.constants import EMPLOYMENT_TYPE_CHOICES
from jobs.models import Category, Job


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "title",
            "category",
            "location",
            "description",
            "responsibilities",
            "skills",
            "employment_type",
            "experience_min",
            "experience_max",
            "salary_min",
            "salary_max",
            "status",
            "application_deadline",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "responsibilities": forms.Textarea(attrs={"rows": 4}),
            "application_deadline": forms.DateInput(attrs={"type": "date"}),
        }

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

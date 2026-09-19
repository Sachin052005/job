from django import forms

from companies.models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "description", "industry", "website", "location", "founded_year", "size", "logo"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }

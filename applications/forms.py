from django import forms

from applications.models import Application


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["cover_letter", "resume"]
        widgets = {
            "cover_letter": forms.Textarea(attrs={"rows": 5, "placeholder": "Why are you a great fit for this role?"}),
        }


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status"]

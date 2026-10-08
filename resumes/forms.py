from django import forms

from core.validators import validate_resume_file
from resumes.models import Resume


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["title", "file"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Python Developer Resume"}),
        }


class ResumeRenameForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["title"]


class JobMatchForm(forms.Form):
    """All three Job Description sources the spec requires (section 43): an
    existing NammaCareer job, pasted text, or an uploaded PDF/DOCX. Exactly
    one must be supplied - never guesses which the student meant."""

    job = forms.ModelChoiceField(queryset=None, required=False, empty_label="Select a job", widget=forms.Select(attrs={"class": "form-select"}))
    pasted_text = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 6, "placeholder": "Paste the job description here"}))
    jd_file = forms.FileField(required=False, validators=[validate_resume_file], widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.constants import JOB_STATUS_PUBLISHED
        from jobs.models import Job

        self.fields["job"].queryset = Job.objects.filter(status=JOB_STATUS_PUBLISHED).select_related("company")

    def clean(self):
        cleaned_data = super().clean()
        sources = [cleaned_data.get("job"), cleaned_data.get("pasted_text", "").strip(), cleaned_data.get("jd_file")]
        provided = [s for s in sources if s]
        if not provided:
            raise forms.ValidationError("Select a job, paste a job description, or upload one.")
        if len(provided) > 1:
            raise forms.ValidationError("Choose only one job description source.")
        return cleaned_data

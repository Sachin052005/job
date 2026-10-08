from django import forms

from core.constants import EMPLOYMENT_TYPE_CHOICES, JOB_BADGE_CHOICES
from jobs.models import Job, JobDomain, JobSubdomain


class SubdomainSelect(forms.Select):
    """Tags each <option> with the owning domain's identifier (pk, or slug
    when the field uses to_field_name="slug") so a page's JS can show only
    the subdomains belonging to the selected domain (spec section 14)
    without a round trip. The JS compares this against the domain <select>'s
    own option values, which use the same identifier."""

    def _domain_by_subdomain_value(self):
        if not hasattr(self, "_domain_map"):
            to_field_name = getattr(self.choices, "field", None) and self.choices.field.to_field_name
            domain_field = f"domain__{to_field_name}" if to_field_name else "domain_id"
            key_field = to_field_name or "pk"
            self._domain_map = dict(self.choices.queryset.values_list(key_field, domain_field))
        return self._domain_map

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        if value:
            domain_value = self._domain_by_subdomain_value().get(value.value if hasattr(value, "value") else value)
            if domain_value:
                option["attrs"]["data-domain"] = domain_value
        return option


class JobForm(forms.ModelForm):
    badges = forms.MultipleChoiceField(
        choices=JOB_BADGE_CHOICES, required=False, widget=forms.CheckboxSelectMultiple
    )
    domain = forms.ModelChoiceField(
        queryset=JobDomain.objects.filter(is_active=True), empty_label="Select a domain",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_domain"}),
    )
    subdomain = forms.ModelChoiceField(
        queryset=JobSubdomain.objects.filter(is_active=True).select_related("domain"),
        empty_label="Select a subdomain",
        widget=SubdomainSelect(attrs={"class": "form-select", "id": "id_subdomain"}),
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "domain",
            "subdomain",
            "location",
            "work_mode",
            "description",
            "responsibilities",
            "skills",
            "preferred_skills",
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

        # A job's subdomain must belong to its selected domain (spec section
        # 14) - enforced server-side, not just by the JS that filters the
        # <select> options, so a tampered/forged POST is still rejected.
        domain = cleaned_data.get("domain")
        subdomain = cleaned_data.get("subdomain")
        if domain and subdomain and subdomain.domain_id != domain.id:
            self.add_error("subdomain", "Selected subdomain does not belong to the selected domain.")
        return cleaned_data

    def save(self, commit=True):
        job = super().save(commit=False)
        job.badges = ",".join(self.cleaned_data.get("badges", []))
        if commit:
            job.save()
        return job


class JobSearchForm(forms.Form):
    keyword = forms.CharField(required=False, label="", widget=forms.TextInput(
        attrs={"placeholder": "Job title, skills, or company", "class": "form-control"}
    ))
    location = forms.CharField(required=False, label="", widget=forms.TextInput(
        attrs={"placeholder": "Location", "class": "form-control"}
    ))
    domain = forms.ModelChoiceField(
        required=False, queryset=JobDomain.objects.filter(is_active=True), to_field_name="slug",
        empty_label="All Domains", widget=forms.Select(attrs={"class": "form-select", "id": "id_search_domain"}),
    )
    subdomain = forms.ModelChoiceField(
        required=False, queryset=JobSubdomain.objects.filter(is_active=True), to_field_name="slug",
        empty_label="All Subdomains",
        widget=SubdomainSelect(attrs={"class": "form-select", "id": "id_search_subdomain"}),
    )
    employment_type = forms.ChoiceField(
        required=False, choices=[("", "Any Employment Type")] + EMPLOYMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    experience = forms.TypedChoiceField(
        required=False, coerce=int, empty_value=None, label="Experience",
        choices=[
            ("", "Any Experience"),
            ("0", "Fresher (0 years)"),
            ("1", "Up to 1 year"),
            ("2", "Up to 2 years"),
            ("3", "Up to 3 years"),
            ("5", "Up to 5 years"),
            ("8", "Up to 8 years"),
            ("10", "Up to 10 years"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    salary_min = forms.TypedChoiceField(
        required=False, coerce=int, empty_value=None, label="Salary",
        choices=[
            ("", "Any Salary"),
            ("300000", "₹3 LPA & above"),
            ("600000", "₹6 LPA & above"),
            ("1000000", "₹10 LPA & above"),
            ("1500000", "₹15 LPA & above"),
            ("2500000", "₹25 LPA & above"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    freshers_only = forms.BooleanField(required=False)
    remote_only = forms.BooleanField(required=False)
    walkin_only = forms.BooleanField(required=False)
    urgent_only = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        # A search for domain=IT with subdomain=Medical Coder must not leak
        # through: drop the mismatched subdomain rather than erroring out a
        # filter form, so the domain filter alone still applies.
        domain = cleaned_data.get("domain")
        subdomain = cleaned_data.get("subdomain")
        if domain and subdomain and subdomain.domain_id != domain.id:
            cleaned_data["subdomain"] = None
        return cleaned_data

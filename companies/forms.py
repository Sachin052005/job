from django import forms

from companies.models import Company, CompanyOffice, CompanyProductService, CompanyReview, CompanySalary


class CompanyForm(forms.ModelForm):
    """Company classification/profile fields (spec sections 25-27) - industry
    and company_type here are the single source of truth the companies:list
    filters (?industry=, ?company_type=) query against, so this is the only
    place HR needs to edit them for every "X Companies" filter to reflect
    reality."""

    class Meta:
        model = Company
        fields = [
            "name", "description", "industry", "sub_industry", "company_type",
            "technologies", "website", "location", "founded_year", "size", "logo",
        ]
        labels = {"description": "Company Overview"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Tell students what your company does..."}),
            "industry": forms.TextInput(attrs={"placeholder": "e.g. IT, Fintech, Healthcare"}),
            "sub_industry": forms.TextInput(attrs={"placeholder": "e.g. SaaS, EdTech"}),
            "technologies": forms.TextInput(attrs={"placeholder": "e.g. Python, Django, AWS (comma-separated)"}),
        }


class CompanyContentForm(forms.ModelForm):
    """Overview + Culture content, edited from the Company Management page (spec sections 3/5)."""

    class Meta:
        model = Company
        fields = ["description", "culture", "work_environment"]
        labels = {
            "description": "Company Overview",
            "culture": "Culture Description",
            "work_environment": "Work Environment",
        }
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 5, "placeholder": "e.g. ABC Technologies is a software development company..."}
            ),
            "culture": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe your company's culture and values."}),
            "work_environment": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe the day-to-day work style."}),
        }


class CompanyOfficeForm(forms.ModelForm):
    class Meta:
        model = CompanyOffice
        fields = [
            "name",
            "office_type",
            "is_headquarters",
            "address",
            "city",
            "state",
            "country",
            "pincode",
            "contact_phone",
            "contact_email",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class CompanySalaryForm(forms.ModelForm):
    class Meta:
        model = CompanySalary
        fields = ["role", "salary_range", "experience_level", "employment_type", "location", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class CompanyProductServiceForm(forms.ModelForm):
    class Meta:
        model = CompanyProductService
        fields = ["item_type", "name", "description", "link", "image"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class CompanyReviewForm(forms.ModelForm):
    RATING_CHOICES = [(i, str(i)) for i in range(5, 0, -1)]

    rating = forms.ChoiceField(choices=RATING_CHOICES, widget=forms.RadioSelect, label="Your Rating")

    class Meta:
        model = CompanyReview
        fields = ["rating", "content", "image"]
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Share your experience working at this company"}
            ),
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 10:
            raise forms.ValidationError("Please share a bit more detail about your experience (at least 10 characters).")
        return content

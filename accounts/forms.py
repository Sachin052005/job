from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from accounts.models import Profile
from core.constants import ROLE_CHOICES

User = get_user_model()


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
            "website_url",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "linkedin_url": forms.URLInput(attrs={"placeholder": "https://www.linkedin.com/in/yourname"}),
            "github_url": forms.URLInput(attrs={"placeholder": "https://github.com/yourname"}),
            "portfolio_url": forms.URLInput(attrs={"placeholder": "https://yourportfolio.com"}),
            "website_url": forms.URLInput(attrs={"placeholder": "https://yourwebsite.com"}),
        }

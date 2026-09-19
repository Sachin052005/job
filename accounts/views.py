from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView, UpdateView

from accounts.forms import ProfileForm, RegisterForm, UserUpdateForm
from accounts.models import Profile
from core.permissions import JobSeekerRequiredMixin
from services.ats_service import analyze_resume_text, external_profile_status, extract_resume_text


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Welcome to Naukri! Your account has been created.")
        return response


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        context["profile"] = profile
        context["missing_sections"] = profile.missing_sections()
        context["link_status"] = {
            "linkedin": external_profile_status(profile.linkedin_url, "linkedin"),
            "github": external_profile_status(profile.github_url, "github"),
            "portfolio": "available" if profile.portfolio_url else "not_provided",
            "website": "available" if profile.website_url else "not_provided",
        }
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["user_form"] = UserUpdateForm(self.request.POST, instance=self.request.user)
        else:
            context["user_form"] = UserUpdateForm(instance=self.request.user)
        context["next_url"] = self._safe_next_url()
        return context

    def _safe_next_url(self):
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            return next_url
        return None

    def form_valid(self, form):
        user_form = UserUpdateForm(self.request.POST, instance=self.request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(self.request, "Profile updated successfully.")
            return super().form_valid(form)
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return self._safe_next_url() or str(self.success_url)


class ResumeAnalysisView(JobSeekerRequiredMixin, TemplateView):
    """Student's own resume ATS readiness report - no job comparison, just the
    resume itself (Resume Dashboard's "Analyze Resume" action).
    """
    template_name = "accounts/resume_analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        resume_text, resume_error = extract_resume_text(profile.resume)
        context["profile"] = profile
        context["analysis"] = analyze_resume_text(resume_text, resume_error)
        return context

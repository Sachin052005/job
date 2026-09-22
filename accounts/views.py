import logging
import secrets
from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordResetView
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView, View

from accounts.google_oauth import GoogleOAuthError, build_authorization_url, exchange_code_for_userinfo
from accounts.models import SocialAccount
from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER

from accounts.forms import (
    AccomplishmentForm,
    CandidateSkillForm,
    CareerPreferenceForm,
    EducationForm,
    InternshipForm,
    JobAlertForm,
    LanguageForm,
    ProfileForm,
    ProjectForm,
    RecruiterProfileForm,
    RegisterForm,
    UserSettingsNotificationsForm,
    UserSettingsPrivacyForm,
    UserSettingsThemeForm,
    UserUpdateForm,
    WorkExperienceForm,
)
from accounts.models import (
    Accomplishment,
    CandidateSkill,
    CareerPreference,
    Education,
    Internship,
    JobAlert,
    Language,
    Profile,
    Project,
    RecruiterProfile,
    UserSettings,
    WorkExperience,
)
from core.permissions import EmployerRequiredMixin, JobSeekerRequiredMixin

logger = logging.getLogger(__name__)


class NammaCareerLoginView(LoginView):
    """The single login page for the whole site - students, HR, and the
    manual admin panel all authenticate here (there is no separate
    /admin-login/). After Django authenticates the user, a staff or
    superuser account is sent to the admin panel; everyone else keeps the
    existing `next`/LOGIN_REDIRECT_URL behaviour unchanged.
    """

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return reverse("adminpanel:dashboard")

        url = super().get_success_url()
        # A non-admin can't reach the admin panel by passing
        # ?next=/admin-panel/... to this login page - AdminRequiredMixin
        # would 403 them there anyway, but there's no reason to send a
        # normal user to that URL in the first place.
        if url.startswith(reverse("adminpanel:dashboard")):
            return resolve_url(self.get_default_redirect_url())
        return url


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Welcome to Naukri! Your account has been created.")
        return response


class PasswordResetRequestView(PasswordResetView):
    """Django's built-in PasswordResetView, hardened against SMTP failures.

    If the Gmail SMTP send raises (bad credentials, network issue, etc.) we
    still redirect to the generic "check your email" page and log the real
    error server-side, so a delivery failure can't be used to tell whether
    an email address has an account (account enumeration).
    """

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except (SMTPException, OSError) as exc:
            logger.error("Password reset email failed to send: %s", exc)
            return redirect(self.get_success_url())


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        context["profile"] = profile
        context["missing_sections"] = profile.missing_sections()
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


class OwnedProfileRecordMixin:
    """Shared CRUD scoping for the candidate profile's structured sub-records.

    Ensures a candidate can only ever see/edit/delete records on their own
    Profile (no pk-in-URL IDOR: another user's record simply 404s), and marks
    the profile as meaningfully updated on every real change.
    """

    success_url = reverse_lazy("accounts:profile")

    def get_queryset(self):
        return super().get_queryset().filter(profile=self.request.user.profile)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # DeleteView's form (Django >= 5) is a plain Form with no .instance.
        if hasattr(form, "instance"):
            form.instance.profile = self.request.user.profile
        return form

    def form_valid(self, form):
        # `profile` isn't a form field, so Django's automatic validate_unique()
        # excludes it - a duplicate (profile, name) row only surfaces as an
        # IntegrityError at save time, not as a clean form error. Catch it
        # here (inside a savepoint so the outer test/request transaction
        # survives) and report it the way a normal validation error would.
        try:
            with transaction.atomic():
                response = super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "This already exists on your profile.")
            return self.form_invalid(form)
        self.request.user.profile.touch_last_updated()
        return response

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        request.user.profile.touch_last_updated()
        return response


class CareerPreferenceEditView(JobSeekerRequiredMixin, UpdateView):
    model = CareerPreference
    form_class = CareerPreferenceForm
    template_name = "accounts/profile_sections/record_form.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        profile = self.request.user.profile
        return getattr(profile, "career_preference", None) or CareerPreference(profile=profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Career Preferences"
        return context

    def form_valid(self, form):
        form.instance.profile = self.request.user.profile
        response = super().form_valid(form)
        self.request.user.profile.touch_last_updated()
        return response


class EducationCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = Education
    form_class = EducationForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Education"}


class EducationUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = Education
    form_class = EducationForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Education"}


class EducationDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = Education
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "education entry"}


class WorkExperienceCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = WorkExperience
    form_class = WorkExperienceForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Experience"}


class WorkExperienceUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = WorkExperience
    form_class = WorkExperienceForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Experience"}


class WorkExperienceDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = WorkExperience
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "experience entry"}


class ProjectCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Project"}


class ProjectUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Project"}


class ProjectDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = Project
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "project"}


class InternshipCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = Internship
    form_class = InternshipForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Internship"}


class InternshipUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = Internship
    form_class = InternshipForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Internship"}


class InternshipDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = Internship
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "internship"}


class AccomplishmentCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = Accomplishment
    form_class = AccomplishmentForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Accomplishment"}


class AccomplishmentUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = Accomplishment
    form_class = AccomplishmentForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Accomplishment"}


class AccomplishmentDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = Accomplishment
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "accomplishment"}


class LanguageCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = Language
    form_class = LanguageForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Language"}


class LanguageUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = Language
    form_class = LanguageForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Language"}


class LanguageDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = Language
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "language"}


class CandidateSkillCreateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, CreateView):
    model = CandidateSkill
    form_class = CandidateSkillForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Add Skill"}


class CandidateSkillUpdateView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, UpdateView):
    model = CandidateSkill
    form_class = CandidateSkillForm
    template_name = "accounts/profile_sections/record_form.html"
    extra_context = {"title": "Edit Skill"}


class CandidateSkillDeleteView(OwnedProfileRecordMixin, JobSeekerRequiredMixin, DeleteView):
    model = CandidateSkill
    template_name = "accounts/profile_sections/record_confirm_delete.html"
    extra_context = {"title": "skill"}


# ---------------------------------------------------------------------------
# Job Alerts (spec section 38)
# ---------------------------------------------------------------------------


class JobAlertListView(LoginRequiredMixin, ListView):
    model = JobAlert
    template_name = "accounts/job_alert_list.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return JobAlert.objects.filter(user=self.request.user)


class JobAlertCreateView(LoginRequiredMixin, CreateView):
    model = JobAlert
    form_class = JobAlertForm
    template_name = "accounts/job_alert_form.html"
    success_url = reverse_lazy("job_alerts:list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Job alert created.")
        return super().form_valid(form)


class JobAlertUpdateView(LoginRequiredMixin, UpdateView):
    model = JobAlert
    form_class = JobAlertForm
    template_name = "accounts/job_alert_form.html"
    success_url = reverse_lazy("job_alerts:list")

    def get_queryset(self):
        return JobAlert.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Job alert updated.")
        return super().form_valid(form)


class JobAlertDeleteView(LoginRequiredMixin, DeleteView):
    model = JobAlert
    template_name = "accounts/job_alert_confirm_delete.html"
    success_url = reverse_lazy("job_alerts:list")

    def get_queryset(self):
        return JobAlert.objects.filter(user=self.request.user)


class JobAlertToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
        alert.is_active = not alert.is_active
        alert.save(update_fields=["is_active"])
        messages.success(request, "Job alert status updated.")
        return redirect("job_alerts:list")


# ---------------------------------------------------------------------------
# Settings (spec sections 39-46)
# ---------------------------------------------------------------------------


class SettingsAccountView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/settings/account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "account"
        context["user_form"] = kwargs.get("user_form") or UserUpdateForm(instance=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Account details updated successfully.")
            return redirect("settings:account")
        return self.render_to_response(self.get_context_data(user_form=form))


class UserSettingsRequiredMixin:
    """Guarantees `self.user_settings` exists even for accounts created before
    the UserSettings model/signal existed (pre-existing users never got a row
    backfilled automatically) - this is what was crashing Appearance/
    Notifications/Privacy with RelatedObjectDoesNotExist for any such user.
    Belt-and-suspenders alongside the accounts.0005 data migration below,
    since any future user-creation path that bypasses the post_save signal
    (bulk_create, raw SQL, fixtures) would otherwise reintroduce this bug.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.user_settings, _ = UserSettings.objects.get_or_create(user=request.user)
        return super().dispatch(request, *args, **kwargs)


class SettingsSecurityPasswordView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/settings/security.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("settings:security_password")

    def get_context_data(self, **kwargs):
        from accounts.google_oauth import is_configured

        context = super().get_context_data(**kwargs)
        context["active"] = "security"
        context["google_oauth_configured"] = is_configured()
        return context

    def form_valid(self, form):
        messages.success(self.request, "Password changed successfully.")
        return super().form_valid(form)


class SettingsAppearanceView(LoginRequiredMixin, UserSettingsRequiredMixin, TemplateView):
    template_name = "accounts/settings/appearance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "appearance"
        context["theme_form"] = kwargs.get("theme_form") or UserSettingsThemeForm(instance=self.user_settings)
        return context

    def post(self, request, *args, **kwargs):
        form = UserSettingsThemeForm(request.POST, instance=self.user_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Appearance updated successfully.")
            return redirect("settings:appearance")
        return self.render_to_response(self.get_context_data(theme_form=form))


class SettingsNotificationsView(LoginRequiredMixin, UserSettingsRequiredMixin, TemplateView):
    template_name = "accounts/settings/notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "notifications"
        context["form"] = kwargs.get("form") or UserSettingsNotificationsForm(instance=self.user_settings)
        return context

    def post(self, request, *args, **kwargs):
        form = UserSettingsNotificationsForm(request.POST, instance=self.user_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Notification settings updated.")
            return redirect("settings:notifications")
        return self.render_to_response(self.get_context_data(form=form))


class SettingsPrivacyView(LoginRequiredMixin, UserSettingsRequiredMixin, TemplateView):
    template_name = "accounts/settings/privacy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "privacy"
        context["form"] = kwargs.get("form") or UserSettingsPrivacyForm(instance=self.user_settings)
        return context

    def post(self, request, *args, **kwargs):
        form = UserSettingsPrivacyForm(request.POST, instance=self.user_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Privacy settings updated.")
            return redirect("settings:privacy")
        return self.render_to_response(self.get_context_data(form=form))


class SettingsApplicationPreferencesView(JobSeekerRequiredMixin, TemplateView):
    template_name = "accounts/settings/application_preferences.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active"] = "application_preferences"
        profile = self.request.user.profile
        preference = getattr(profile, "career_preference", None) or CareerPreference(profile=profile)
        context["form"] = kwargs.get("form") or CareerPreferenceForm(instance=preference)
        return context

    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        preference = getattr(profile, "career_preference", None) or CareerPreference(profile=profile)
        form = CareerPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.instance.profile = profile
            form.save()
            messages.success(request, "Application preferences updated.")
            return redirect("settings:application_preferences")
        return self.render_to_response(self.get_context_data(form=form))


# ---------------------------------------------------------------------------
# Performance (spec section 36) + Recruiter profile (spec section 29, 37)
# ---------------------------------------------------------------------------


class StudentPerformanceView(JobSeekerRequiredMixin, TemplateView):
    template_name = "accounts/performance.html"

    def get_context_data(self, **kwargs):
        from applications.models import Application

        context = super().get_context_data(**kwargs)
        applications = Application.objects.filter(applicant=self.request.user)
        context["applications_count"] = applications.count()
        context["shortlisted_count"] = applications.filter(status="shortlisted").count()
        # Search Appearances / Recruiter Actions / Profile Views require dedicated
        # event tracking that doesn't exist in this codebase yet - reported as 0
        # (real, not fabricated) rather than inventing numbers.
        context["profile_views"] = 0
        context["search_appearances"] = 0
        context["recruiter_actions"] = 0
        return context


class RecruiterProfileEditView(EmployerRequiredMixin, UpdateView):
    model = RecruiterProfile
    form_class = RecruiterProfileForm
    template_name = "accounts/recruiter_profile_form.html"
    success_url = reverse_lazy("accounts:recruiter_profile_edit")

    def get_object(self, queryset=None):
        profile, _ = RecruiterProfile.objects.get_or_create(user=self.request.user)
        if not profile.company_id and hasattr(self.request.user, "company"):
            profile.company = self.request.user.company
            profile.save(update_fields=["company"])
        return profile

    def form_valid(self, form):
        messages.success(self.request, "Recruiter profile updated successfully.")
        return super().form_valid(form)


class RecruiterPerformanceView(EmployerRequiredMixin, TemplateView):
    template_name = "accounts/recruiter_performance.html"

    def get_context_data(self, **kwargs):
        from applications.models import Application
        from jobs.models import Job

        context = super().get_context_data(**kwargs)
        jobs = Job.objects.filter(employer=self.request.user)
        applications = Application.objects.filter(job__employer=self.request.user)
        context["job_views"] = sum(jobs.values_list("views_count", flat=True))
        context["applications_count"] = applications.count()
        context["shortlists_count"] = applications.filter(status="shortlisted").count()
        context["interviews_count"] = applications.filter(status="interview").count()
        return context


# ---------------------------------------------------------------------------
# Google OAuth (spec sections 51-55)
# ---------------------------------------------------------------------------

_GOOGLE_STATE_SESSION_KEY = "google_oauth_state"
_GOOGLE_LINK_SESSION_KEY = "google_oauth_link_user_id"


def _google_redirect_uri(request):
    return request.build_absolute_uri(reverse("accounts:google_callback"))


class GoogleLoginView(View):
    """Starts the login/signup flow. Uses a random `state` stored in the
    session to prevent CSRF on the callback (spec section 55)."""

    def get(self, request):
        state = secrets.token_urlsafe(32)
        request.session[_GOOGLE_STATE_SESSION_KEY] = state
        request.session.pop(_GOOGLE_LINK_SESSION_KEY, None)
        return redirect(build_authorization_url(_google_redirect_uri(request), state))


class GoogleLinkView(LoginRequiredMixin, View):
    """Starts the flow for an already-authenticated user linking their Google
    identity from Settings - the user is already verified by being logged in
    (spec section 54)."""

    def get(self, request):
        state = secrets.token_urlsafe(32)
        request.session[_GOOGLE_STATE_SESSION_KEY] = state
        request.session[_GOOGLE_LINK_SESSION_KEY] = request.user.id
        return redirect(build_authorization_url(_google_redirect_uri(request), state))


class GoogleCallbackView(View):
    def get(self, request):
        expected_state = request.session.pop(_GOOGLE_STATE_SESSION_KEY, None)
        received_state = request.GET.get("state")
        if not expected_state or not received_state or not secrets.compare_digest(expected_state, received_state):
            messages.error(request, "Google sign-in could not be verified. Please try again.")
            return redirect("accounts:login")

        code = request.GET.get("code")
        if not code:
            messages.error(request, "Google sign-in was cancelled or failed.")
            return redirect("accounts:login")

        try:
            userinfo = exchange_code_for_userinfo(code, _google_redirect_uri(request))
        except GoogleOAuthError as exc:
            messages.error(request, str(exc))
            return redirect("accounts:login")

        sub = userinfo["sub"]
        email = userinfo["email"]

        link_user_id = request.session.pop(_GOOGLE_LINK_SESSION_KEY, None)
        if link_user_id:
            return self._handle_link(request, link_user_id, sub, email)
        return self._handle_login(request, sub, email, userinfo)

    def _handle_link(self, request, link_user_id, sub, email):
        if not request.user.is_authenticated or request.user.id != link_user_id:
            messages.error(request, "Google sign-in could not be verified. Please try again.")
            return redirect("accounts:login")
        if SocialAccount.objects.filter(provider="google", provider_user_id=sub).exclude(user=request.user).exists():
            messages.error(request, "This Google account is already linked to a different NammaCareer account.")
            return redirect("settings:security_password")
        SocialAccount.objects.get_or_create(
            provider="google", provider_user_id=sub, defaults={"user": request.user, "email": email}
        )
        messages.success(request, "Your Google account has been linked.")
        return redirect("settings:security_password")

    def _handle_login(self, request, sub, email, userinfo):
        User = get_user_model()

        social_account = SocialAccount.objects.filter(provider="google", provider_user_id=sub).select_related("user").first()
        if social_account:
            login(request, social_account.user)
            return self._redirect_after_login(social_account.user)

        # One Google identity must map to one NammaCareer user (spec section
        # 54) - if the email already belongs to a password account that
        # hasn't linked Google yet, don't silently create a duplicate user or
        # auto-link without the owner being authenticated first.
        if User.objects.filter(email__iexact=email).exists():
            messages.info(
                request,
                "An account with this email already exists. Log in with your password, then link Google "
                "from Settings > Security.",
            )
            return redirect("accounts:login")

        username = self._unique_username(User, email)
        user = User.objects.create(
            username=username,
            email=email,
            first_name=userinfo.get("given_name", "")[:150],
            last_name=userinfo.get("family_name", "")[:150],
        )
        user.set_unusable_password()
        user.save()
        SocialAccount.objects.create(provider="google", provider_user_id=sub, user=user, email=email)

        login(request, user)
        messages.success(request, "Welcome to NammaCareer!")
        return redirect("accounts:google_welcome")

    @staticmethod
    def _unique_username(User, email):
        base = slugify(email.split("@")[0]) or "user"
        username = base
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base}{suffix}"
        return username

    @staticmethod
    def _redirect_after_login(user):
        # DashboardHomeView already branches by role (student vs recruiter
        # dashboard template) - a single redirect target is correct here.
        return redirect("dashboard:home")


class GoogleWelcomeView(LoginRequiredMixin, TemplateView):
    """New Google sign-up role selection (spec section 53)."""

    template_name = "accounts/google_welcome.html"

    def post(self, request, *args, **kwargs):
        choice = request.POST.get("choice")
        if choice not in ("job_seeker", "employer"):
            messages.error(request, "Please choose an option to continue.")
            return self.get(request, *args, **kwargs)

        profile = request.user.profile
        profile.role = choice
        profile.save(update_fields=["role"])

        if choice == ROLE_JOB_SEEKER:
            return redirect("accounts:profile_edit")
        return redirect("companies:create")

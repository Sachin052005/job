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
    """Profile Performance dashboard. The chart and the activity list below
    it are two views of the *same* filtered queryset for the *same*
    timezone-aware [start, end) window - never two independently-computed
    numbers that can drift apart (spec sections 23-26): whichever range the
    student picks (Today/Yesterday/Last 7/30/90 Days/Custom) narrows both
    together, and the summary tiles above them too."""

    template_name = "accounts/performance.html"

    RANGE_CHOICES = {"today", "yesterday", "7d", "30d", "90d", "custom"}
    RANGE_LABELS = {
        "today": "Today", "yesterday": "Yesterday", "7d": "Last 7 Days",
        "30d": "Last 30 Days", "90d": "Last 90 Days", "custom": "Custom Range",
    }

    def _resolve_range(self):
        from datetime import datetime, time, timedelta

        from django.utils import timezone
        from django.utils.dateparse import parse_date

        today = timezone.localdate()
        range_key = self.request.GET.get("range", "30d")
        if range_key not in self.RANGE_CHOICES:
            range_key = "30d"

        start_date = end_date = today
        if range_key == "today":
            start_date = end_date = today
        elif range_key == "yesterday":
            start_date = end_date = today - timedelta(days=1)
        elif range_key == "7d":
            start_date, end_date = today - timedelta(days=6), today
        elif range_key == "90d":
            start_date, end_date = today - timedelta(days=89), today
        elif range_key == "custom":
            start_date = parse_date(self.request.GET.get("start", "") or "") or (today - timedelta(days=29))
            end_date = parse_date(self.request.GET.get("end", "") or "") or today
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            if end_date > today:
                end_date = today
        else:  # "30d"
            start_date, end_date = today - timedelta(days=29), today

        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
        return range_key, start_date, end_date, start_dt, end_dt

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        from django.utils import timezone

        from activity.models import StudentActivity, StudentProfileView, StudentSearchAppearance
        from applications.models import Application
        from core.constants import (
            ACTIVITY_PROFILE_UPDATE,
            ACTIVITY_PROFILE_VIEW,
            ACTIVITY_RESUME_DOWNLOAD,
            ACTIVITY_RESUME_VIEW,
            ACTIVITY_SEARCH_APPEARANCE,
            RECRUITER_ACTION_EVENT_TYPES,
        )

        context = super().get_context_data(**kwargs)
        user = self.request.user
        range_key, start_date, end_date, start_dt, end_dt = self._resolve_range()

        applications = Application.objects.filter(applicant=user)
        activities = StudentActivity.objects.filter(
            student=user, created_at__gte=start_dt, created_at__lte=end_dt
        )
        window_applications = applications.filter(applied_at__gte=start_dt, applied_at__lte=end_dt)

        context["range_key"] = range_key
        context["range_label"] = self.RANGE_LABELS[range_key]
        context["range_start"] = start_date
        context["range_end"] = end_date
        context["range_options"] = list(self.RANGE_LABELS.items())

        context["applications_count"] = window_applications.count()
        context["shortlisted_count"] = window_applications.filter(status="shortlisted").count()
        context["profile_views"] = StudentProfileView.objects.filter(
            student=user, viewed_at__gte=start_dt, viewed_at__lte=end_dt
        ).count()
        context["search_appearances"] = StudentSearchAppearance.objects.filter(
            student=user, created_at__gte=start_dt, created_at__lte=end_dt
        ).count()
        context["recruiter_actions"] = activities.filter(event_type__in=RECRUITER_ACTION_EVENT_TYPES).count()
        context["resume_views"] = activities.filter(event_type=ACTIVITY_RESUME_VIEW).count()
        context["resume_downloads"] = activities.filter(event_type=ACTIVITY_RESUME_DOWNLOAD).count()
        context["profile_updates"] = activities.filter(event_type=ACTIVITY_PROFILE_UPDATE).count()

        # Activity Overview chart: 3 real series (Profile Views, Search
        # Appearances, Recruiter Actions) built from the exact same
        # `activities` queryset the timeline below uses - never a second,
        # independently-computed number. Hourly buckets for a single-day
        # range (Today/Yesterday), daily buckets otherwise. Bucketed in
        # Python via timezone.localtime() (not a DB-side Trunc+tzinfo)
        # since MySQL's CONVERT_TZ needs its timezone tables loaded, which
        # isn't guaranteed on every deployment - this stays correct for
        # Asia/Kolkata regardless of the DB server's own tz-table state.
        # Only `event_type`/`created_at` are pulled per row (values()), not
        # full model instances.
        single_day = start_date == end_date
        # Recruiter-driven events not already covered by their own line
        # (Profile Views, Search Appearances) - avoids double-counting the
        # same event on two series at once.
        recruiter_action_types = {
            t for t in RECRUITER_ACTION_EVENT_TYPES
            if t not in (ACTIVITY_PROFILE_VIEW, ACTIVITY_SEARCH_APPEARANCE)
        }
        profile_view_counts, search_appearance_counts, recruiter_action_counts = {}, {}, {}
        for row in activities.values("event_type", "created_at"):
            local_dt = timezone.localtime(row["created_at"])
            bucket_key = local_dt.hour if single_day else local_dt.date()
            event_type = row["event_type"]
            if event_type == ACTIVITY_PROFILE_VIEW:
                target = profile_view_counts
            elif event_type == ACTIVITY_SEARCH_APPEARANCE:
                target = search_appearance_counts
            elif event_type in recruiter_action_types:
                target = recruiter_action_counts
            else:
                continue
            target[bucket_key] = target.get(bucket_key, 0) + 1

        if single_day:
            chart_labels = [f"{h:02d}:00" for h in range(24)]
            chart_tooltip_labels = [f"{start_date.strftime('%d %b %Y')}, {h:02d}:00" for h in range(24)]
            bucket_keys = list(range(24))
        else:
            chart_labels, chart_tooltip_labels, bucket_keys = [], [], []
            day = start_date
            while day <= end_date:
                chart_labels.append(day.strftime("%b %d"))
                chart_tooltip_labels.append(day.strftime("%d %b %Y"))
                bucket_keys.append(day)
                day += timedelta(days=1)

        chart_series = [
            {
                "key": "profile_views", "label": "Profile Views", "color": "#159a78",
                "data": [profile_view_counts.get(key, 0) for key in bucket_keys],
            },
            {
                "key": "search_appearances", "label": "Search Appearances", "color": "#08785d",
                "data": [search_appearance_counts.get(key, 0) for key in bucket_keys],
            },
            {
                "key": "recruiter_actions", "label": "Recruiter Actions", "color": "#172235",
                "data": [recruiter_action_counts.get(key, 0) for key in bucket_keys],
            },
        ]
        context["chart_series"] = chart_series
        context["chart_labels"] = chart_labels
        context["chart_has_data"] = any(any(series["data"]) for series in chart_series)
        context["chart_json"] = {
            "labels": chart_labels,
            "tooltipLabels": chart_tooltip_labels,
            "series": chart_series,
        }

        # Activity details list (spec section 24): the same `activities` +
        # `window_applications` rows the chart/tiles above were computed
        # from - selecting a range always narrows both together.
        timeline = []
        for activity in activities.select_related("company", "job", "application"):
            timeline.append({"timestamp": activity.created_at, "text": self._activity_text(activity)})
        for application in window_applications.select_related("job", "job__company"):
            timeline.append(
                {"timestamp": application.applied_at, "text": f"You applied for {application.job.title}"}
            )
        timeline.sort(key=lambda item: item["timestamp"], reverse=True)
        context["timeline"] = self._group_timeline(timeline[:100])
        return context

    @staticmethod
    def _activity_text(activity):
        from core.constants import (
            ACTIVITY_APPLICATION_STATUS,
            ACTIVITY_CONTACTED,
            ACTIVITY_INTERVIEW,
            ACTIVITY_PROFILE_UPDATE,
            ACTIVITY_PROFILE_VIEW,
            ACTIVITY_RESUME_DOWNLOAD,
            ACTIVITY_RESUME_VIEW,
            ACTIVITY_SEARCH_APPEARANCE,
            ACTIVITY_SHORTLISTED,
        )

        actor = activity.actor_label()
        if activity.event_type == ACTIVITY_PROFILE_VIEW:
            return f"{actor} viewed your profile"
        if activity.event_type == ACTIVITY_SEARCH_APPEARANCE:
            return f"You appeared in a search by {actor}"
        if activity.event_type == ACTIVITY_RESUME_VIEW:
            return f"{actor} viewed your resume"
        if activity.event_type == ACTIVITY_RESUME_DOWNLOAD:
            return f"{actor} downloaded your resume"
        if activity.event_type == ACTIVITY_SHORTLISTED:
            job_title = activity.job.title if activity.job_id else "a role"
            return f"You were shortlisted for {job_title}"
        if activity.event_type == ACTIVITY_CONTACTED:
            return f"{actor} contacted you"
        if activity.event_type == ACTIVITY_INTERVIEW:
            job_title = activity.job.title if activity.job_id else "a role"
            return f"Interview scheduled for {job_title}"
        if activity.event_type == ACTIVITY_APPLICATION_STATUS:
            job_title = activity.job.title if activity.job_id else "your application"
            status = (activity.metadata or {}).get("new_status", "")
            status_label = status.replace("_", " ").title() if status else "updated"
            return f"Your application for {job_title} was updated to {status_label}"
        if activity.event_type == ACTIVITY_PROFILE_UPDATE:
            return "You updated your profile"
        return activity.get_event_type_display()

    @staticmethod
    def _group_timeline(items):
        from django.utils import timezone

        today = timezone.localdate()
        groups = []
        group_index = {}
        for item in items:
            day = timezone.localtime(item["timestamp"]).date()
            delta = (today - day).days
            if delta == 0:
                label = "Today"
            elif delta == 1:
                label = "Yesterday"
            else:
                label = f"{delta} days ago"
            if label not in group_index:
                group_index[label] = {"label": label, "items": []}
                groups.append(group_index[label])
            group_index[label]["items"].append(item)
        return groups


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

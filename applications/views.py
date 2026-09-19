from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, View

from applications.forms import ApplicationForm, ApplicationStatusForm
from applications.models import Application
from applications.services import ensure_match_snapshot
from core.constants import APPLICATION_STATUS_CHOICES, APPLICATIONS_PAGE_SIZE, APPLIED_VIA_EASY_APPLY
from core.permissions import EmployerRequiredMixin, JobSeekerRequiredMixin
from jobs.models import Job
from services.ats_service import (
    analyze_github_profile,
    analyze_job_match,
    analyze_linkedin_url,
    extract_resume_text,
    generate_resume_suggestions,
)
from services.search_service import filter_applications


def application_guard_redirect(request, job):
    """Returns a redirect response if the user cannot apply to this job right now, else None.

    Shared by the manual apply flow and Easy Apply so both enforce the same
    "job open" / "no duplicate application" constraints.
    """
    if not request.user.is_authenticated:
        return None
    if not job.is_open():
        messages.error(request, "This job is no longer accepting applications.")
        return redirect("jobs:detail", pk=job.pk)
    if Application.objects.filter(job=job, applicant=request.user).exists():
        messages.info(request, "You have already applied to this job.")
        return redirect("jobs:detail", pk=job.pk)
    return None


class ApplyView(JobSeekerRequiredMixin, CreateView):
    model = Application
    form_class = ApplicationForm
    template_name = "applications/application_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        guard_response = application_guard_redirect(request, self.job)
        if guard_response:
            return guard_response
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job"] = self.job
        return context

    def form_valid(self, form):
        form.instance.job = self.job
        form.instance.applicant = self.request.user
        messages.success(self.request, "Application submitted successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("applications:detail", kwargs={"pk": self.object.pk})


class MyApplicationsListView(JobSeekerRequiredMixin, ListView):
    model = Application
    template_name = "applications/my_applications.html"
    context_object_name = "applications"
    paginate_by = APPLICATIONS_PAGE_SIZE

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user).select_related("job", "job__company")


class EasyApplyReviewView(JobSeekerRequiredMixin, TemplateView):
    """Step 1-3 of Easy Apply: profile-completeness gate, then a review page
    showing the profile snapshot that will be submitted plus the ATS job
    match analysis and resume suggestions - no re-typing of information.
    """
    template_name = "applications/easy_apply_review.html"

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        guard_response = application_guard_redirect(request, self.job)
        if guard_response:
            return guard_response
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        profile = request.user.profile
        if not profile.is_easy_apply_ready():
            missing = profile.missing_easy_apply_fields()
            messages.warning(
                request,
                "Complete your profile before applying. Your profile is missing: " + ", ".join(missing) + ".",
            )
            next_url = reverse("jobs:detail", kwargs={"pk": self.job.pk})
            return redirect(f"{reverse('accounts:profile_edit')}?next={next_url}")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        resume_text, resume_error = extract_resume_text(profile.resume)
        match_result = analyze_job_match(profile, resume_text, self.job, resume_error)
        context.update(
            {
                "job": self.job,
                "profile": profile,
                "match": match_result,
                "suggestions": generate_resume_suggestions(match_result),
                "resume_error": resume_error,
            }
        )
        return context


class EasyApplyConfirmView(JobSeekerRequiredMixin, View):
    """Step 4 of Easy Apply: server-side re-validation + re-computation (never
    trusting a client-submitted score), then create the Application exactly
    like the manual flow does, reusing the profile's resume without a re-upload.
    """

    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        guard_response = application_guard_redirect(request, job)
        if guard_response:
            return guard_response

        profile = request.user.profile
        if not profile.is_easy_apply_ready():
            missing = profile.missing_easy_apply_fields()
            messages.warning(
                request,
                "Complete your profile before applying. Your profile is missing: " + ", ".join(missing) + ".",
            )
            next_url = reverse("jobs:detail", kwargs={"pk": job.pk})
            return redirect(f"{reverse('accounts:profile_edit')}?next={next_url}")

        application = Application(
            job=job,
            applicant=request.user,
            cover_letter=profile.summary,
            applied_via=APPLIED_VIA_EASY_APPLY,
            resume=profile.resume.name,
        )
        try:
            application.full_clean()
        except ValidationError:
            messages.error(request, "Could not submit your application. Please review your profile and try again.")
            return redirect("jobs:detail", pk=job.pk)

        try:
            application.save()
        except IntegrityError:
            messages.info(request, "You have already applied to this job.")
            return redirect("jobs:detail", pk=job.pk)

        ensure_match_snapshot(application, job)
        messages.success(request, "Application submitted successfully.")
        return redirect(f"{reverse('applications:detail', kwargs={'pk': application.pk})}?submitted=1")


class JobApplicationsListView(EmployerRequiredMixin, ListView):
    template_name = "applications/job_applications.html"
    context_object_name = "applications"
    paginate_by = APPLICATIONS_PAGE_SIZE

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        if request.user.is_authenticated and self.job.employer_id != request.user.id:
            raise PermissionDenied("You do not own this job posting.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Application.objects.filter(job=self.job).select_related("applicant", "applicant__profile")
        queryset = filter_applications(queryset, self.request.GET)
        self.sort = self.request.GET.get("sort", "newest")
        if self.sort == "match":
            applications = list(queryset)
            for application in applications:
                ensure_match_snapshot(application, self.job)
            applications.sort(key=lambda a: (a.match_snapshot or {}).get("overall_percent", 0), reverse=True)
            return applications
        if self.sort == "oldest":
            return queryset.order_by("applied_at")
        return queryset.order_by("-applied_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job"] = self.job
        context["sort"] = getattr(self, "sort", "newest")
        context["status_choices"] = APPLICATION_STATUS_CHOICES
        context["querystring"] = self._querystring_without_page()

        # Explicitly compute snapshots for the current page - don't rely on
        # queryset-evaluation ordering relative to the quick_review pass below.
        page_applications = list(context[self.context_object_name])
        for application in page_applications:
            ensure_match_snapshot(application, self.job)
        context[self.context_object_name] = page_applications

        all_applications = list(
            Application.objects.filter(job=self.job).select_related("applicant", "applicant__profile")
        )
        for application in all_applications:
            ensure_match_snapshot(application, self.job)
        context["quick_review"] = sorted(
            all_applications, key=lambda a: (a.match_snapshot or {}).get("overall_percent", 0), reverse=True
        )[:5]
        context["total_applicant_count"] = len(all_applications)
        return context

    def _querystring_without_page(self):
        query = self.request.GET.copy()
        query.pop("page", None)
        return query.urlencode()


class ApplicationDetailView(DetailView):
    model = Application
    template_name = "applications/application_detail.html"
    context_object_name = "application"

    def get_queryset(self):
        return Application.objects.select_related("job", "job__company", "applicant", "applicant__profile")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        is_applicant = self.object.applicant_id == request.user.id
        is_employer = self.object.job.employer_id == request.user.id
        if not (is_applicant or is_employer):
            raise PermissionDenied("You do not have access to this application.")
        context = self.get_context_data(object=self.object)
        context["status_form"] = ApplicationStatusForm(instance=self.object)
        context["is_employer_view"] = is_employer
        context["just_submitted"] = request.GET.get("submitted") == "1"
        if is_employer:
            candidate_profile = self.object.applicant.profile
            context["match"] = ensure_match_snapshot(self.object, self.object.job)
            context["github_analysis"] = analyze_github_profile(
                candidate_profile.github_url, self.object.job.skills_list()
            )
            context["linkedin_analysis"] = analyze_linkedin_url(candidate_profile.linkedin_url)
        return self.render_to_response(context)


class UpdateApplicationStatusView(EmployerRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(Application.objects.select_related("job"), pk=pk)
        if application.job.employer_id != request.user.id:
            raise PermissionDenied("You do not own this job posting.")
        form = ApplicationStatusForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, "Application status updated.")
        else:
            messages.error(request, "Could not update application status.")
        return redirect("applications:detail", pk=application.pk)

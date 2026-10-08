import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, View

from applications.forms import ApplicationForm, ApplicationStatusForm, InterviewForm, InterviewResultForm, RecruiterNoteForm
from applications.models import Application, Interview, RecruiterNote
from core.constants import (
    APPLICATION_STATUS_CHOICES,
    APPLICATION_STATUS_HIRED,
    APPLICATIONS_PAGE_SIZE,
    APPLIED_VIA_EASY_APPLY,
    APPLIED_VIA_MANUAL,
)
from core.permissions import EmployerRequiredMixin, JobSeekerRequiredMixin
from core.utils import unique_upload_path
from jobs.models import Job
from notifications.services import notify_new_application, send_application_status_email
from services.search_service import filter_applications
from services.skill_match_service import calculate_skill_match

logger = logging.getLogger(__name__)


def application_guard_redirect(request, job):
    """Returns a redirect response if the user cannot apply to this job right now, else None.

    Shared by the manual apply flow and Easy Apply so both enforce the same
    "job open" / "no duplicate application" constraints (spec sections 20/21).
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


def _profile_initial(user):
    """Prefill convenience for the manual Apply form only - values remain editable
    and are never re-copied from the profile once submitted (spec section 12)."""
    profile = getattr(user, "profile", None)
    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
    }
    if profile:
        initial.update(
            {
                "phone": profile.phone,
                "location": profile.location,
                "current_title": profile.headline,
                "experience_years": profile.experience_years,
                "skills": profile.skills,
                "linkedin_url": profile.linkedin_url,
                "github_url": profile.github_url,
                "portfolio_url": profile.portfolio_url,
                "cover_letter": profile.summary,
            }
        )
    return initial


def _easy_apply_snapshot(user):
    """Read-only Easy Apply source-of-truth data pulled straight from the profile
    (spec section 1) - never re-typed by the student."""
    profile = user.profile
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": profile.phone,
        "location": profile.location,
        "current_title": profile.headline,
        "experience_years": profile.experience_years,
        "skills": profile.skills,
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "portfolio_url": profile.portfolio_url,
        "cover_letter": profile.summary,
        "resume_name": profile.resume.name.rsplit("/", 1)[-1] if profile.resume else "",
    }


def _pending_manual_application_key(job_id):
    return f"pending_manual_application_{job_id}"


class ApplyView(JobSeekerRequiredMixin, CreateView):
    """Manual "Apply" flow (spec section 10/11): the existing full form, unchanged,
    except that a valid submission no longer saves immediately - it stages the
    data and shows a skill-match confirmation screen first (ApplyConfirmView
    performs the actual save)."""

    model = Application
    form_class = ApplicationForm
    template_name = "applications/application_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        guard_response = application_guard_redirect(request, self.job)
        if guard_response:
            return guard_response
        if not self.job.allows_apply():
            messages.error(request, "This job only accepts Easy Apply.")
            return redirect("jobs:detail", pk=self.job.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        pending = self.request.session.get(_pending_manual_application_key(self.job.pk))
        if pending:
            return {k: v for k, v in pending.items() if k not in ("resume_path", "resume_name")}
        return _profile_initial(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job"] = self.job
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if form.is_valid():
            return self._stage_for_confirmation(form)
        return self.render_to_response(self.get_context_data(form=form))

    def _stage_for_confirmation(self, form):
        """Validate + compute the deterministic skill match, but don't create the
        Application yet (spec section 11) - store the validated data server-side
        (session) and require an explicit Confirm & Apply POST to persist it."""
        cleaned = form.cleaned_data.copy()
        resume_file = cleaned.pop("resume")

        upload_to = unique_upload_path("application_resumes")
        resume_path = default_storage.save(upload_to(None, resume_file.name), resume_file)

        pending = dict(cleaned)
        pending["experience_years"] = cleaned.get("experience_years") or 0
        pending["resume_path"] = resume_path
        pending["resume_name"] = resume_file.name
        self.request.session[_pending_manual_application_key(self.job.pk)] = pending

        match_result = calculate_skill_match(pending.get("skills", ""), self.job.skills_list())

        return render(
            self.request,
            "applications/application_confirm.html",
            {"job": self.job, "pending": pending, "match": match_result},
        )

    def get_success_url(self):
        return reverse("applications:detail", kwargs={"pk": self.object.pk})


class ApplyConfirmView(JobSeekerRequiredMixin, View):
    """Manual Apply, step 2 (spec section 11): only this explicit "Confirm & Apply"
    POST creates the Application. The skill match is recalculated here from the
    server-held staged data - the browser's copy is never trusted (spec section 21)."""

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        guard_response = application_guard_redirect(request, self.job)
        if guard_response:
            return guard_response
        if not self.job.allows_apply():
            messages.error(request, "This job only accepts Easy Apply.")
            return redirect("jobs:detail", pk=self.job.pk)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        key = _pending_manual_application_key(self.job.pk)
        pending = request.session.get(key)
        if not pending:
            messages.error(request, "Your application session has expired. Please apply again.")
            return redirect("applications:apply", job_id=self.job.pk)

        match_result = calculate_skill_match(pending.get("skills", ""), self.job.skills_list())

        application = Application(
            job=self.job,
            applicant=request.user,
            first_name=pending.get("first_name", ""),
            last_name=pending.get("last_name", ""),
            email=pending.get("email", ""),
            phone=pending.get("phone", ""),
            location=pending.get("location", ""),
            current_company=pending.get("current_company", ""),
            current_title=pending.get("current_title", ""),
            experience_years=pending.get("experience_years") or 0,
            education_summary=pending.get("education_summary", ""),
            skills=pending.get("skills", ""),
            linkedin_url=pending.get("linkedin_url", ""),
            github_url=pending.get("github_url", ""),
            portfolio_url=pending.get("portfolio_url", ""),
            cover_letter=pending.get("cover_letter", ""),
            applied_via=APPLIED_VIA_MANUAL,
        )
        application.resume.name = pending["resume_path"]
        application.apply_skill_match(match_result)
        application.save()

        del request.session[key]

        # Notify the responsible recruiter, not the applicant (spec: student
        # applies -> HR is notified, the student is not).
        notify_new_application(application)
        # Confirmation email to the applicant themself - reuses the same
        # centralized status-email dispatch every later status change goes
        # through (old_status=None: there's no prior status for a brand new
        # application).
        send_application_status_email(application, old_status=None, new_status=application.status)

        # ATS processing happens after the application is already saved and
        # the user is about to be redirected to a success page - a parsing
        # failure here can never turn a valid application into a lost one.
        from services.application_ats_service import process_application_ats

        try:
            process_application_ats(application)
        except Exception:
            logger.exception("Unexpected ATS pipeline failure for application_id=%s", application.pk)

        messages.success(request, "Application submitted successfully.")
        return redirect(f"{reverse('applications:detail', kwargs={'pk': application.pk})}?submitted=1")


class ApplyCancelView(JobSeekerRequiredMixin, View):
    """Discards a staged manual application (spec section 11 "Back & Edit"/Cancel)."""

    def post(self, request, *args, **kwargs):
        job = get_object_or_404(Job, pk=kwargs["job_id"])
        pending = request.session.pop(_pending_manual_application_key(job.pk), None)
        if pending and pending.get("resume_path"):
            default_storage.delete(pending["resume_path"])
        return redirect("jobs:detail", pk=job.pk)


class MyApplicationsListView(JobSeekerRequiredMixin, ListView):
    model = Application
    template_name = "applications/my_applications.html"
    context_object_name = "applications"
    paginate_by = APPLICATIONS_PAGE_SIZE

    def get_queryset(self):
        queryset = Application.objects.filter(applicant=self.request.user).select_related("job", "job__company")
        self.tab = self.request.GET.get("tab", "all")
        if self.tab != "all":
            queryset = queryset.filter(status=self.tab)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tab"] = getattr(self, "tab", "all")
        context["status_choices"] = APPLICATION_STATUS_CHOICES
        return context


class EasyApplyReviewView(JobSeekerRequiredMixin, TemplateView):
    """Easy Apply (spec sections 1/2/8/9): profile-completeness gate, then a
    read-only review of the profile snapshot + deterministic skill match - no
    re-typing, no editing here. Only an explicit "Confirm & Apply" POST creates
    the Application.
    """

    template_name = "applications/easy_apply_review.html"

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job, pk=kwargs["job_id"])
        guard_response = application_guard_redirect(request, self.job)
        if guard_response:
            return guard_response
        if not self.job.allows_easy_apply():
            messages.error(request, "This job only accepts full applications (Apply).")
            return redirect("jobs:detail", pk=self.job.pk)
        return super().dispatch(request, *args, **kwargs)

    def _profile_incomplete_redirect(self, request):
        profile = request.user.profile
        if profile.is_easy_apply_ready():
            return None
        missing = profile.missing_easy_apply_fields()
        messages.warning(
            request,
            "Complete your profile before applying. Missing: " + ", ".join(missing) + ".",
        )
        next_url = reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk})
        return redirect(f"{reverse('accounts:profile_edit')}?next={next_url}")

    def get(self, request, *args, **kwargs):
        redirect_response = self._profile_incomplete_redirect(request)
        if redirect_response:
            return redirect_response
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        context["job"] = self.job
        context["profile"] = profile
        context["snapshot"] = _easy_apply_snapshot(self.request.user)
        context["match"] = calculate_skill_match(profile.effective_skills_list(), self.job.skills_list())
        return context

    def post(self, request, *args, **kwargs):
        redirect_response = self._profile_incomplete_redirect(request)
        if redirect_response:
            return redirect_response

        profile = request.user.profile
        snapshot = _easy_apply_snapshot(request.user)
        match_result = calculate_skill_match(profile.effective_skills_list(), self.job.skills_list())

        application = Application(
            job=self.job,
            applicant=request.user,
            first_name=snapshot["first_name"],
            last_name=snapshot["last_name"],
            email=snapshot["email"],
            phone=snapshot["phone"],
            location=snapshot["location"],
            current_title=snapshot["current_title"],
            experience_years=snapshot["experience_years"],
            skills=snapshot["skills"],
            linkedin_url=snapshot["linkedin_url"],
            github_url=snapshot["github_url"],
            portfolio_url=snapshot["portfolio_url"],
            cover_letter=snapshot["cover_letter"],
            applied_via=APPLIED_VIA_EASY_APPLY,
        )
        application.resume.name = profile.resume.name
        application.apply_skill_match(match_result)
        application.save()

        # Notify the responsible recruiter, not the applicant (spec: student
        # applies -> HR is notified, the student is not). Same rule as the
        # manual Apply flow (ApplyConfirmView) - both methods notify identically.
        notify_new_application(application)
        # Same submission-confirmation email as the manual Apply flow.
        send_application_status_email(application, old_status=None, new_status=application.status)

        from services.application_ats_service import process_application_ats

        try:
            process_application_ats(application)
        except Exception:
            logger.exception("Unexpected ATS pipeline failure for application_id=%s", application.pk)

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

    SORT_MAP = {
        "newest": "-applied_at",
        "oldest": "applied_at",
        "ats_score": "-ats_score",
        "experience": "-experience_years",
        "name": "first_name",
    }

    def get_queryset(self):
        queryset = Application.objects.filter(job=self.job).select_related("applicant", "applicant__profile")
        queryset = filter_applications(queryset, self.request.GET)
        self.sort = self.request.GET.get("sort", "newest")
        return queryset.order_by(self.SORT_MAP.get(self.sort, "-applied_at"))

    def get_context_data(self, **kwargs):
        from services.ats_analytics_service import pipeline_analytics

        context = super().get_context_data(**kwargs)
        analytics = pipeline_analytics(self.job)
        context["job"] = self.job
        context["sort"] = getattr(self, "sort", "newest")
        context["status_choices"] = APPLICATION_STATUS_CHOICES
        context["querystring"] = self._querystring_without_page()
        context["total_applicant_count"] = analytics["total_applications"]
        context["status_counts"] = analytics["status_counts"]
        context["analytics"] = analytics
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
        context["status_history"] = self.object.status_history.select_related("changed_by")
        context["can_review_company"] = self._can_review_company(is_applicant)
        if is_employer:
            context["recruiter_notes"] = self.object.recruiter_notes.select_related("author")
            context["note_form"] = RecruiterNoteForm()
            context["interviews"] = self.object.interviews.select_related("interviewer")
        return self.render_to_response(context)

    def _can_review_company(self, is_applicant):
        """Verified Student Review eligibility (spec sections 9/10/22/32): only
        once this exact application has reached the project's Hired status."""
        if not is_applicant or self.object.status != APPLICATION_STATUS_HIRED:
            return False
        from companies.models import CompanyReview

        return not CompanyReview.objects.filter(
            company=self.object.job.company, applicant=self.object.applicant
        ).exists()


class _EmployerApplicationMixin:
    """Shared owner-check for every recruiter-only action on an
    Application (notes, interviews) - the requester must be the employer
    who owns the job this application belongs to (spec: prevent an
    unauthorized recruiter from reaching another company's candidate
    data)."""

    def get_application(self, pk):
        application = get_object_or_404(
            Application.objects.select_related("job", "job__company", "applicant"), pk=pk
        )
        if application.job.employer_id != self.request.user.id:
            raise PermissionDenied("You do not own this job posting.")
        return application


class ApplicationResumeView(View):
    """Serves an application's resume file through a permission-checked,
    activity-tracked view instead of the raw media URL (spec: prevent
    unauthorized resume download / IDOR - the direct media URL had no
    access check at all). `mode=view` streams inline, `mode=download`
    forces Content-Disposition: attachment. Only the resume's own
    applicant or the job's employer may reach it; only the employer's
    view/download is recorded on the applicant's activity timeline (the
    applicant viewing their own resume is not a "recruiter action")."""

    def get(self, request, pk, mode):
        if not request.user.is_authenticated:
            raise PermissionDenied("Login required.")
        application = get_object_or_404(
            Application.objects.select_related("job", "job__company", "applicant"), pk=pk
        )
        is_applicant = application.applicant_id == request.user.id
        is_employer = application.job.employer_id == request.user.id
        if not (is_applicant or is_employer):
            raise PermissionDenied("You do not have access to this resume.")
        if not application.resume:
            raise Http404("No resume on this application.")

        if is_employer:
            from activity.services import record_resume_download, record_resume_view

            if mode == "download":
                record_resume_download(application.applicant, request.user, application.job.company, application)
            else:
                record_resume_view(application.applicant, request.user, application.job.company, application)

        filename = application.resume.name.rsplit("/", 1)[-1]
        return FileResponse(application.resume.open("rb"), as_attachment=(mode == "download"), filename=filename)


class RecruiterNoteCreateView(EmployerRequiredMixin, _EmployerApplicationMixin, View):
    def post(self, request, pk):
        application = self.get_application(pk)
        form = RecruiterNoteForm(request.POST)
        if form.is_valid():
            RecruiterNote.objects.create(application=application, author=request.user, text=form.cleaned_data["text"])
            messages.success(request, "Note added.")
        else:
            messages.error(request, "Note could not be saved.")
        return redirect(f"{reverse('applications:detail', kwargs={'pk': pk})}#notes")


class RecruiterNoteDeleteView(EmployerRequiredMixin, _EmployerApplicationMixin, View):
    def post(self, request, pk, note_id):
        application = self.get_application(pk)
        note = get_object_or_404(RecruiterNote, pk=note_id, application=application)
        if note.author_id != request.user.id:
            raise PermissionDenied("You can only delete your own notes.")
        note.delete()
        messages.success(request, "Note deleted.")
        return redirect(f"{reverse('applications:detail', kwargs={'pk': pk})}#notes")


class InterviewCreateView(EmployerRequiredMixin, _EmployerApplicationMixin, View):
    def post(self, request, pk):
        application = self.get_application(pk)
        form = InterviewForm(request.POST, company=application.job.company)
        if form.is_valid():
            interview = form.save(commit=False)
            interview.application = application
            interview.created_by = request.user
            interview.save()

            from notifications.services import notify_interview_scheduled

            notify_interview_scheduled(interview)

            from activity.models import StudentActivity
            from core.constants import ACTIVITY_INTERVIEW

            StudentActivity.objects.create(
                student=application.applicant, event_type=ACTIVITY_INTERVIEW, recruiter=request.user,
                company=application.job.company, application=application, job=application.job,
            )

            messages.success(request, "Interview scheduled. The candidate has been notified.")
        else:
            messages.error(request, "Interview could not be scheduled. Please check the details.")
        return redirect(f"{reverse('applications:interview_list')}?application={pk}")


class InterviewUpdateResultView(EmployerRequiredMixin, _EmployerApplicationMixin, View):
    def post(self, request, pk, interview_id):
        application = self.get_application(pk)
        interview = get_object_or_404(Interview, pk=interview_id, application=application)
        form = InterviewResultForm(request.POST, instance=interview)
        if form.is_valid():
            form.save()
            messages.success(request, "Interview updated.")
        else:
            messages.error(request, "Could not update interview.")
        return redirect(f"{reverse('applications:interview_list')}?application={pk}")


class InterviewListView(EmployerRequiredMixin, ListView):
    """Dedicated HR "Interviews" page (spec: HR navigation should have its
    own Interviews entry, distinct from a specific candidate's application
    detail page) - every interview across every job this employer owns,
    with the same schedule/result actions the application detail page used
    to embed. Scoped identically to every other employer-facing view here
    (job.employer_id == request.user.id - see _EmployerApplicationMixin) so
    one recruiter can never see another company's interviews."""

    model = Interview
    template_name = "applications/interview_list.html"
    context_object_name = "interviews"
    paginate_by = APPLICATIONS_PAGE_SIZE

    def get_queryset(self):
        queryset = Interview.objects.filter(application__job__employer=self.request.user).select_related(
            "application__job", "application__job__company", "application__applicant", "interviewer",
        )
        self.filter_application_id = self.request.GET.get("application")
        if self.filter_application_id:
            queryset = queryset.filter(application_id=self.filter_application_id)
        return queryset.order_by("-scheduled_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applications = list(
            Application.objects.filter(job__employer=self.request.user)
            .select_related("job", "job__company")
            .order_by("-applied_at")[:200]
        )
        context["applications"] = applications
        context["filter_application_id"] = self.filter_application_id

        interview_form = InterviewForm()
        companies = {a.job.company for a in applications}
        if companies:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            interviewer_q = Q(pk=self.request.user.pk)
            for company in companies:
                interviewer_q |= Q(pk=company.owner_id) | Q(recruiter_profile__company=company)
            interview_form.fields["interviewer"].queryset = User.objects.filter(interviewer_q).distinct()
        context["interview_form"] = interview_form
        context["result_form"] = InterviewResultForm()
        return context


class UpdateApplicationStatusView(EmployerRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(Application.objects.select_related("job"), pk=pk)
        if application.job.employer_id != request.user.id:
            raise PermissionDenied("You do not own this job posting.")
        # Deliberately not bound to `instance=application`: ModelForm._post_clean()
        # mutates the bound instance's fields during is_valid() itself (before any
        # save()), which would make application.status already equal the new
        # value by the time record_status_change() reads the "old" status below.
        form = ApplicationStatusForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            # record_status_change() itself notifies the applicant (spec: HR
            # changes status -> student notified, HR is not) - see
            # Application.record_status_change() in applications/models.py.
            result = application.record_status_change(
                new_status, changed_by=request.user, note=form.cleaned_data.get("note", "")
            )
            if not result["changed"]:
                messages.success(request, "Application status updated.")
            elif result["email_sent"]:
                messages.success(
                    request,
                    f"Application status updated to {application.get_status_display()}. "
                    "Candidate notification email sent.",
                )
            else:
                messages.success(
                    request,
                    f"Application status updated to {application.get_status_display()}, but the "
                    "candidate notification email could not be sent.",
                )
        else:
            messages.error(request, "Could not update application status.")
        return redirect("applications:detail", pk=application.pk)

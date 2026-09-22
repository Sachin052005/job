from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView

from accounts.models import Profile
from activity.services import record_profile_view, record_search_appearance
from core.constants import (
    CAREER_EMPLOYMENT_TYPE_CHOICES,
    EXPERIENCE_LEVEL_CHOICES,
    PAGE_SIZE,
    PROFILE_VIEW_SOURCE_CHOICES,
    PROFILE_VIEW_SOURCE_DIRECT,
    WORK_MODE_CHOICES,
)
from core.permissions import EmployerRequiredMixin
from services.search_service import filter_students


class CandidateSearchView(EmployerRequiredMixin, ListView):
    """Recruiter-facing candidate search (spec sections 8-10)."""

    model = Profile
    template_name = "students/search.html"
    context_object_name = "candidates"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        return filter_students(Profile.objects.all(), self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["querystring"] = self._querystring_without_page()
        context["total_candidate_count"] = self.get_queryset().count()
        context["experience_level_choices"] = EXPERIENCE_LEVEL_CHOICES
        context["employment_type_choices"] = CAREER_EMPLOYMENT_TYPE_CHOICES
        context["work_mode_choices"] = WORK_MODE_CHOICES

        search_query = " ".join(
            value
            for value in (self.request.GET.get("name"), self.request.GET.get("skills"), self.request.GET.get("job_title"))
            if value
        )
        company = getattr(self.request.user, "company", None)
        for candidate in context["candidates"]:
            record_search_appearance(candidate.user, self.request.user, company, search_query)
        return context

    def _querystring_without_page(self):
        query = self.request.GET.copy()
        query.pop("page", None)
        return query.urlencode()


class CandidateDetailView(EmployerRequiredMixin, DetailView):
    """Recruiter-facing view of a single candidate's profile (spec section
    11). Records a StudentProfileView (deduplicated) and, via
    activity.services, the resulting student activity/notification. Reached
    from candidate search (?source=candidate_search) or an application's
    "View Student Profile" button (?source=application)."""

    model = Profile
    template_name = "students/detail.html"
    context_object_name = "candidate"

    def get_queryset(self):
        return Profile.objects.select_related("user", "career_preference").prefetch_related(
            "education_records",
            "experience_records",
            "projects",
            "internships",
            "accomplishments",
            "languages",
            "structured_skills",
        )

    def get(self, request, *args, **kwargs):
        candidate = get_object_or_404(self.get_queryset(), user_id=kwargs["user_id"])
        settings_obj = getattr(candidate.user, "settings", None)
        if settings_obj is not None and not settings_obj.recruiters_can_view_profile:
            messages.error(request, "This candidate has restricted their profile visibility.")
            return redirect("students:search")

        self.object = candidate
        source = request.GET.get("source", PROFILE_VIEW_SOURCE_DIRECT)
        if source not in {key for key, _ in PROFILE_VIEW_SOURCE_CHOICES}:
            source = PROFILE_VIEW_SOURCE_DIRECT
        company = getattr(request.user, "company", None)
        record_profile_view(candidate.user, request.user, company, source)

        context = self.get_context_data(object=candidate)
        context["candidate_can_contact"] = settings_obj is None or settings_obj.recruiters_can_contact
        context["candidate_can_download_resume"] = settings_obj is None or settings_obj.recruiters_can_download_resume
        return self.render_to_response(context)

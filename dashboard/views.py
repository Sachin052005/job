from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from applications.models import Application
from core.constants import (
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_SHORTLISTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    ROLE_EMPLOYER,
)
from jobs.models import Job
from saved_jobs.models import SavedJob


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    def get_template_names(self):
        if self.request.user.profile.role == ROLE_EMPLOYER:
            return ["dashboard/employer_dashboard.html"]
        return ["dashboard/seeker_dashboard.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.profile.role == ROLE_EMPLOYER:
            company = getattr(user, "company", None)
            jobs = Job.objects.filter(employer=user) if company else Job.objects.none()
            applications = Application.objects.filter(job__employer=user).select_related("job", "applicant", "applicant__profile")
            context.update(
                {
                    "company": company,
                    "total_jobs": jobs.count(),
                    "active_jobs": jobs.filter(status="published").count(),
                    "total_applications": applications.count(),
                    "pending_applications": applications.filter(
                        status__in=[APPLICATION_STATUS_APPLIED, APPLICATION_STATUS_UNDER_REVIEW]
                    ).count(),
                    "shortlisted_count": applications.filter(status=APPLICATION_STATUS_SHORTLISTED).count(),
                    "interview_count": applications.filter(status=APPLICATION_STATUS_INTERVIEW).count(),
                    "recent_jobs": jobs.order_by("-created_at")[:5],
                    "recent_applications": applications.order_by("-applied_at")[:5],
                    "profiles_with_resume": applications.exclude(resume="").count(),
                    "profiles_with_linkedin": applications.exclude(linkedin_url="").count(),
                    "profiles_with_github": applications.exclude(github_url="").count(),
                }
            )
        else:
            profile = user.profile
            applications = Application.objects.filter(applicant=user).select_related("job", "job__company")
            context.update(
                {
                    "profile": profile,
                    "profile_completion_percent": profile.completion_percent(),
                    "total_applications": applications.count(),
                    "shortlisted_count": applications.filter(status=APPLICATION_STATUS_SHORTLISTED).count(),
                    "interview_count": applications.filter(status=APPLICATION_STATUS_INTERVIEW).count(),
                    "saved_jobs_count": SavedJob.objects.filter(user=user).count(),
                    "job_alerts_count": user.job_alerts.filter(is_active=True).count(),
                    "recent_applications": applications.order_by("-applied_at")[:5],
                    "recommended_jobs": Job.objects.filter(status="published").exclude(
                        applications__applicant=user
                    ).select_related("company")[:5],
                    "linkedin_connected": bool(profile.linkedin_url),
                    "github_connected": bool(profile.github_url),
                }
            )
        return context

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from applications.models import Application
from applications.services import ensure_match_snapshot
from core.constants import APPLICATION_STATUS_APPLIED, APPLICATION_STATUS_UNDER_REVIEW, ROLE_EMPLOYER
from jobs.models import Job
from saved_jobs.models import SavedJob
from services.ats_service import analyze_resume_text, extract_resume_text


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
                    "recent_jobs": jobs.order_by("-created_at")[:5],
                    "recent_applications": applications.order_by("-applied_at")[:5],
                    "profiles_with_resume": applications.exclude(resume="").count(),
                    "profiles_with_linkedin": applications.exclude(applicant__profile__linkedin_url="").count(),
                    "profiles_with_github": applications.exclude(applicant__profile__github_url="").count(),
                }
            )
        else:
            profile = user.profile
            applications = Application.objects.filter(applicant=user).select_related("job", "job__company")
            resume_text, resume_error = extract_resume_text(profile.resume)
            resume_analysis = analyze_resume_text(resume_text, resume_error)

            recent_matched = list(applications.select_related("job").order_by("-applied_at")[:5])
            recent_job_matches = []
            for application in recent_matched:
                snapshot = ensure_match_snapshot(application, application.job)
                recent_job_matches.append({"job_title": application.job.title, "percent": snapshot.get("overall_percent", 0)})

            context.update(
                {
                    "profile": profile,
                    "total_applications": applications.count(),
                    "saved_jobs_count": SavedJob.objects.filter(user=user).count(),
                    "recent_applications": applications.order_by("-applied_at")[:5],
                    "recommended_jobs": Job.objects.filter(status="published").exclude(
                        applications__applicant=user
                    ).select_related("company")[:5],
                    "resume_readiness_percent": resume_analysis["readiness_percent"],
                    "linkedin_connected": bool(profile.linkedin_url),
                    "github_connected": bool(profile.github_url),
                    "recent_job_matches": recent_job_matches,
                }
            )
        return context

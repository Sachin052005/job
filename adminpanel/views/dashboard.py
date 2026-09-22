from django.contrib.auth import get_user_model
from django.views.generic import TemplateView

from accounts.models import Profile, RecruiterProfile
from adminpanel.mixins import AdminRequiredMixin
from applications.models import Application
from companies.models import Company, CompanyReview
from core.constants import (
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_SHORTLISTED,
    JOB_STATUS_PUBLISHED,
    ROLE_EMPLOYER,
    ROLE_JOB_SEEKER,
    VERIFICATION_PENDING,
)
from helpcenter.models import Feedback
from jobs.models import Job
from notifications.models import Notification

User = get_user_model()


class DashboardView(AdminRequiredMixin, TemplateView):
    """/admin-panel/ - every figure is a live DB query, never hardcoded
    (spec section 8)."""

    template_name = "adminpanel/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        applications = Application.objects.all()
        ctx.update(
            {
                "total_users": User.objects.count(),
                "student_count": Profile.objects.filter(role=ROLE_JOB_SEEKER).count(),
                "recruiter_count": Profile.objects.filter(role=ROLE_EMPLOYER).count(),
                "company_count": Company.objects.count(),
                "total_jobs": Job.objects.count(),
                "published_jobs": Job.objects.filter(status=JOB_STATUS_PUBLISHED).count(),
                "application_count": applications.count(),
                "shortlisted_count": applications.filter(status=APPLICATION_STATUS_SHORTLISTED).count(),
                "interview_count": applications.filter(status=APPLICATION_STATUS_INTERVIEW).count(),
                "hired_count": applications.filter(status=APPLICATION_STATUS_HIRED).count(),
                "review_count": CompanyReview.objects.count(),
                "unread_notification_count": Notification.objects.filter(is_read=False).count(),
                "feedback_count": Feedback.objects.count(),
                "pending_recruiter_verifications": RecruiterProfile.objects.filter(
                    verification_status=VERIFICATION_PENDING
                ).count(),
                "recent_applications": applications.select_related(
                    "job", "applicant", "job__company"
                ).order_by("-applied_at")[:8],
                "recent_jobs": Job.objects.select_related("company").order_by("-created_at")[:8],
            }
        )
        return ctx

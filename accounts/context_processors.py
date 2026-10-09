def drawer_stats_context(request):
    """Real (not fabricated) counts for the profile side-drawer performance
    cards (spec section 33) - kept cheap since it runs on every page load.
    Shares the same 90-day window and RECRUITER_ACTION_EVENT_TYPES definition
    as accounts.views.StudentPerformanceView (/accounts/performance/), so the
    drawer and the full performance page never disagree.
    """
    if not request.user.is_authenticated:
        return {}
    # Admin accounts are Admin only (spec: superuser/staff never act as
    # job seeker/employer) - skip the student/employer drawer stats
    # entirely rather than falling through to the Profile.role default.
    if request.user.is_staff or request.user.is_superuser:
        return {}
    profile = getattr(request.user, "profile", None)
    if profile is None:
        return {}

    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from applications.models import Application
    from core.constants import (
        APPLICATION_STATUS_INTERVIEW,
        APPLICATION_STATUS_SHORTLISTED,
        RECRUITER_ACTION_EVENT_TYPES,
        ROLE_EMPLOYER,
    )
    from jobs.models import Job

    if profile.role == ROLE_EMPLOYER:
        applications = Application.objects.filter(job__employer=request.user)
        job_views = Job.objects.filter(employer=request.user).aggregate(total=Sum("views_count"))["total"] or 0
        return {
            "drawer_applications_count": applications.count(),
            "drawer_shortlists_count": applications.filter(status=APPLICATION_STATUS_SHORTLISTED).count(),
            "drawer_interviews_count": applications.filter(status=APPLICATION_STATUS_INTERVIEW).count(),
            "drawer_job_views_count": job_views,
        }

    from activity.models import StudentActivity, StudentSearchAppearance

    since = timezone.now() - timedelta(days=90)
    return {
        "drawer_search_appearances_count": StudentSearchAppearance.objects.filter(
            student=request.user, created_at__gte=since
        ).count(),
        "drawer_recruiter_actions_count": StudentActivity.objects.filter(
            student=request.user, created_at__gte=since, event_type__in=RECRUITER_ACTION_EVENT_TYPES
        ).count(),
    }

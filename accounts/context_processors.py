def drawer_stats_context(request):
    """Real (not fabricated) counts for the profile side-drawer performance
    cards (spec section 33) - kept cheap since it runs on every page load.
    """
    if not request.user.is_authenticated:
        return {}
    profile = getattr(request.user, "profile", None)
    if profile is None:
        return {}

    from applications.models import Application
    from core.constants import (
        APPLICATION_STATUS_INTERVIEW,
        APPLICATION_STATUS_SHORTLISTED,
        ROLE_EMPLOYER,
    )

    if profile.role == ROLE_EMPLOYER:
        applications = Application.objects.filter(job__employer=request.user)
        return {
            "drawer_applications_count": applications.count(),
            "drawer_shortlists_count": applications.filter(status=APPLICATION_STATUS_SHORTLISTED).count(),
            "drawer_interviews_count": applications.filter(status=APPLICATION_STATUS_INTERVIEW).count(),
        }
    return {}

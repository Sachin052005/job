"""Recruiter ATS analytics (spec: "Only show metrics when enough real data
exists. Never generate fake analytics."). Every number here is a real
aggregate over Application/ApplicationStatusHistory rows for one job -
nothing is estimated or hardcoded.
"""
from django.db.models import Avg, F

from core.constants import (
    APPLICATION_STATUS_CHOICES,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_SHORTLISTED,
)

# Below this many data points, an average is too noisy to be a meaningful
# "time to X" metric - shown as "Not enough data yet" instead of a number
# that looks precise but isn't.
MIN_SAMPLE_SIZE = 1


def _avg_time_to_status(job, status):
    from applications.models import ApplicationStatusHistory

    rows = (
        ApplicationStatusHistory.objects.filter(application__job=job, new_status=status)
        .annotate(seconds_to_status=F("changed_at") - F("application__applied_at"))
        .values_list("seconds_to_status", flat=True)
    )
    rows = list(rows)
    if len(rows) < MIN_SAMPLE_SIZE:
        return None, len(rows)
    total_seconds = sum(delta.total_seconds() for delta in rows)
    avg_hours = round((total_seconds / len(rows)) / 3600, 1)
    return avg_hours, len(rows)


def pipeline_analytics(job):
    """Applications-by-status counts plus time-to-shortlist/interview/hire
    averages for `job`, computed only from real ApplicationStatusHistory
    rows for this job."""
    from applications.models import Application

    applications = Application.objects.filter(job=job)
    status_counts = {key: applications.filter(status=key).count() for key, _ in APPLICATION_STATUS_CHOICES}

    shortlist_hours, shortlist_n = _avg_time_to_status(job, APPLICATION_STATUS_SHORTLISTED)
    interview_hours, interview_n = _avg_time_to_status(job, APPLICATION_STATUS_INTERVIEW)
    hire_hours, hire_n = _avg_time_to_status(job, APPLICATION_STATUS_HIRED)

    return {
        "total_applications": applications.count(),
        "status_counts": status_counts,
        "avg_ats_score": applications.filter(ats_score__isnull=False).aggregate(avg=Avg("ats_score"))["avg"],
        "time_to_shortlist_hours": shortlist_hours,
        "time_to_shortlist_n": shortlist_n,
        "time_to_interview_hours": interview_hours,
        "time_to_interview_n": interview_n,
        "time_to_hire_hours": hire_hours,
        "time_to_hire_n": hire_n,
    }

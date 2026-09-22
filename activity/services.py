"""Write path for recruiter-action tracking (candidate search appearances,
profile views, and the StudentActivity log they feed). Every call site
(candidate search, "View Student Profile" from an application, ...) should
go through record_search_appearance()/record_profile_view() rather than
creating StudentSearchAppearance/StudentProfileView/StudentActivity rows
directly, so the dedup policy (spec sections 10, 12, 78, 80) and the
resulting student notification (spec section 39) live in exactly one place.
"""
from datetime import timedelta

from django.utils import timezone

from activity.models import StudentActivity, StudentProfileView, StudentSearchAppearance
from core.constants import (
    ACTIVITY_PROFILE_VIEW,
    ACTIVITY_SEARCH_APPEARANCE,
    PROFILE_VIEW_DEDUP_HOURS,
    SEARCH_APPEARANCE_DEDUP_HOURS,
)


def _recent_cutoff(hours):
    return timezone.now() - timedelta(hours=hours)


def record_search_appearance(student, recruiter, company, search_query=""):
    """A student appeared in `recruiter`'s candidate search results. No-op
    (and returns None) if the recruiter is the student themself, or if this
    same (student, recruiter) pair already has an appearance within
    SEARCH_APPEARANCE_DEDUP_HOURS - a re-run search/refresh does not pile up
    duplicate appearances."""
    if recruiter is None or recruiter.pk == student.pk:
        return None
    already_recent = StudentSearchAppearance.objects.filter(
        student=student, recruiter=recruiter, created_at__gte=_recent_cutoff(SEARCH_APPEARANCE_DEDUP_HOURS)
    ).exists()
    if already_recent:
        return None
    appearance = StudentSearchAppearance.objects.create(
        student=student, recruiter=recruiter, company=company, search_query=(search_query or "")[:300]
    )
    StudentActivity.objects.create(
        student=student, event_type=ACTIVITY_SEARCH_APPEARANCE, recruiter=recruiter, company=company
    )
    return appearance


def record_profile_view(student, recruiter, company, source):
    """`recruiter` viewed `student`'s profile. Deduplicated per (student,
    recruiter) within PROFILE_VIEW_DEDUP_HOURS - reloading the same profile
    repeatedly does not create new StudentProfileView/StudentActivity rows
    or re-notify the student (spec section 78, 80). Returns the
    StudentProfileView on a genuinely new view, else None."""
    if recruiter is None or recruiter.pk == student.pk:
        return None
    already_recent = StudentProfileView.objects.filter(
        student=student, recruiter=recruiter, viewed_at__gte=_recent_cutoff(PROFILE_VIEW_DEDUP_HOURS)
    ).exists()
    if already_recent:
        return None
    view = StudentProfileView.objects.create(student=student, recruiter=recruiter, company=company, source=source)
    activity = StudentActivity.objects.create(
        student=student, event_type=ACTIVITY_PROFILE_VIEW, recruiter=recruiter, company=company
    )

    from notifications.services import notify_profile_view

    notify_profile_view(activity)
    return view

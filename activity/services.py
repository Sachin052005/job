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
    ACTIVITY_APPLICATION_STATUS,
    ACTIVITY_INTERVIEW,
    ACTIVITY_PROFILE_VIEW,
    ACTIVITY_RESUME_DOWNLOAD,
    ACTIVITY_RESUME_VIEW,
    ACTIVITY_SEARCH_APPEARANCE,
    ACTIVITY_SHORTLISTED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_SHORTLISTED,
    PROFILE_VIEW_DEDUP_HOURS,
    RESUME_DOWNLOAD_DEDUP_HOURS,
    RESUME_VIEW_DEDUP_HOURS,
    SEARCH_APPEARANCE_DEDUP_HOURS,
)

_STATUS_EVENT_TYPE = {
    APPLICATION_STATUS_SHORTLISTED: ACTIVITY_SHORTLISTED,
    APPLICATION_STATUS_INTERVIEW: ACTIVITY_INTERVIEW,
}


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


def _record_resume_event(student, recruiter, company, application, event_type, dedup_hours, notify):
    """Shared dedup/create/notify logic for resume view + download - a
    recruiter viewing/downloading their own resume (shouldn't happen, but
    defensively) is never counted, and repeated clicks within dedup_hours
    don't inflate the count."""
    if recruiter is None or recruiter.pk == student.pk:
        return None
    already_recent = StudentActivity.objects.filter(
        student=student, recruiter=recruiter, event_type=event_type,
        created_at__gte=_recent_cutoff(dedup_hours),
    ).exists()
    if already_recent:
        return None
    activity = StudentActivity.objects.create(
        student=student, event_type=event_type, recruiter=recruiter, company=company, application=application,
    )
    notify(activity)
    return activity


def record_resume_view(student, recruiter, company, application=None):
    """A recruiter viewed `student`'s resume (spec: RESUME_VIEW / recruiter
    "Resume Viewed" activity)."""
    from notifications.services import notify_resume_view

    return _record_resume_event(
        student, recruiter, company, application, ACTIVITY_RESUME_VIEW, RESUME_VIEW_DEDUP_HOURS, notify_resume_view
    )


def record_resume_download(student, recruiter, company, application=None):
    """A recruiter downloaded `student`'s resume (spec: RESUME_DOWNLOAD /
    recruiter "Resume Downloaded" activity)."""
    from notifications.services import notify_resume_download

    return _record_resume_event(
        student, recruiter, company, application, ACTIVITY_RESUME_DOWNLOAD, RESUME_DOWNLOAD_DEDUP_HOURS,
        notify_resume_download,
    )


def record_application_status_activity(application, new_status, changed_by):
    """An application's status changed - log it on the applicant's activity
    timeline (spec section 21) so the student performance page (spec section
    22) has a real "recruiter action" to show instead of a hardcoded 0.
    Called from Application.record_status_change(), the single choke point
    for every status transition, so this fires exactly once per change
    regardless of who made it (HR view or the admin panel)."""
    event_type = _STATUS_EVENT_TYPE.get(new_status, ACTIVITY_APPLICATION_STATUS)
    company = application.job.company if application.job_id else None
    recruiter = changed_by if changed_by and changed_by.pk != application.applicant_id else None
    return StudentActivity.objects.create(
        student=application.applicant,
        event_type=event_type,
        recruiter=recruiter,
        company=company,
        application=application,
        job=application.job,
        metadata={"new_status": new_status},
    )

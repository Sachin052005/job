"""Notification creation - the single entrypoint every app should call so
per-user notification-category preferences (UserSettings) are always
respected (spec section 22: "When OFF: do not create/send that category of
notification to that user.").

notify_new_application() and notify_application_status_change() are the
centralized helpers for the application lifecycle: submitting an
application notifies the responsible recruiter (never the applicant), and
a status change notifies the applicant (never whoever made the change,
recruiter or admin). Call these instead of create_notification() directly
so the recipient/content rules live in exactly one place.
"""
from core.constants import NOTIFICATION_TYPE_APPLICATION, NOTIFICATION_TYPE_RECRUITER


def create_notification(
    recipient, notification_type, title, message="", job=None, application=None, company=None, actor=None
):
    from notifications.models import Notification

    settings_obj = getattr(recipient, "settings", None)
    if settings_obj is not None and not settings_obj.notifications_enabled_for(notification_type):
        return None

    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        job=job,
        application=application,
        company=company,
        actor=actor,
    )


def notify_new_application(application):
    """A student submitted `application` - notify the job's responsible
    recruiter (Job.employer), never the applicant themselves."""
    job = application.job
    return create_notification(
        job.employer,
        NOTIFICATION_TYPE_APPLICATION,
        "New Job Application",
        f"{application.full_name()} has applied for {job.title}.",
        job=job,
        application=application,
        company=job.company,
    )


def notify_application_status_change(application, old_status, new_status):
    """`application`'s status changed from old_status to new_status - notify
    the applicant, never whoever made the change. A no-op (no notification)
    if the status didn't actually change, so callers can invoke this
    unconditionally without producing duplicate/spurious notifications."""
    if old_status == new_status:
        return None
    job = application.job
    return create_notification(
        application.applicant,
        NOTIFICATION_TYPE_APPLICATION,
        "Application Status Updated",
        f"Your application for {job.title} at {job.company.name} has been updated to "
        f"{application.get_status_display()}.",
        job=job,
        application=application,
        company=job.company,
    )


def notify_profile_view(activity):
    """A recruiter viewed a student's profile (spec sections 12, 39) - notify
    the student, naming the recruiter/company when available via
    StudentActivity.actor_label(). `activity` is the StudentActivity row
    activity.services.record_profile_view() just created, which is already
    deduplicated, so this fires exactly once per genuinely new view."""
    return create_notification(
        activity.student,
        NOTIFICATION_TYPE_RECRUITER,
        "Your profile was viewed",
        f"{activity.actor_label()} viewed your profile.",
        company=activity.company,
        actor=activity.recruiter,
    )

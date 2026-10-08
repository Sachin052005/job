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
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from core.constants import (
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_SELECTED,
    APPLICATION_STATUS_SHORTLISTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    NOTIFICATION_TYPE_APPLICATION,
    NOTIFICATION_TYPE_RECRUITER,
)

logger = logging.getLogger(__name__)


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


def notify_resume_view(activity):
    """A recruiter viewed the student's resume (spec: "Recruiter viewed your
    resume"). `activity` is the StudentActivity row activity.services.
    record_resume_view() just created (already deduplicated)."""
    return create_notification(
        activity.student,
        NOTIFICATION_TYPE_RECRUITER,
        "Your resume was viewed",
        f"{activity.actor_label()} viewed your resume.",
        company=activity.company,
        actor=activity.recruiter,
        application=activity.application,
    )


def notify_resume_download(activity):
    """A recruiter downloaded the student's resume (spec: "Recruiter viewed
    your resume" family - download variant)."""
    return create_notification(
        activity.student,
        NOTIFICATION_TYPE_RECRUITER,
        "Your resume was downloaded",
        f"{activity.actor_label()} downloaded your resume.",
        company=activity.company,
        actor=activity.recruiter,
        application=activity.application,
    )


def notify_ats_processing_complete(application):
    """The ATS finished analyzing `application`'s resume - notify the job's
    responsible recruiter (spec: recruiter notification "ATS processing
    completed"), never the applicant. A no-op if ATS processing failed -
    there's nothing useful to notify the recruiter about in that case."""
    from core.constants import ATS_STATUS_COMPLETE

    if application.ats_status != ATS_STATUS_COMPLETE:
        return None
    job = application.job
    return create_notification(
        job.employer,
        NOTIFICATION_TYPE_APPLICATION,
        "ATS processing completed",
        f"ATS analysis for {application.full_name()}'s application to {job.title} is ready "
        f"({application.ats_score}% compatibility).",
        job=job,
        application=application,
        company=job.company,
    )


def notify_interview_scheduled(interview):
    """A recruiter scheduled `interview` - notify the candidate (spec:
    "Interview scheduled"), never the recruiter who scheduled it."""
    application = interview.application
    job = application.job
    return create_notification(
        application.applicant,
        NOTIFICATION_TYPE_APPLICATION,
        "Interview scheduled",
        f"An interview for {job.title} at {job.company.name} has been scheduled for "
        f"{interview.scheduled_at:%d %b %Y, %H:%M}.",
        job=job,
        application=application,
        company=job.company,
    )


def notify_interview_updated(interview):
    """An already-scheduled interview's details changed - notify the
    candidate (spec: "Interview updated")."""
    application = interview.application
    job = application.job
    return create_notification(
        application.applicant,
        NOTIFICATION_TYPE_APPLICATION,
        "Interview updated",
        f"Your interview for {job.title} at {job.company.name} has been updated - "
        f"now {interview.scheduled_at:%d %b %Y, %H:%M}.",
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


# ---------------------------------------------------------------------------
# Application status emails
#
# Single centralized dispatch point for every student-facing application
# status email (Applied confirmation + every real status transition).
# Application.record_status_change() - the one choke point every status
# change already goes through (HR's update-status view, the admin panel's
# status edit, its bulk actions) - calls send_application_status_email()
# right alongside notify_application_status_change() (the in-app
# notification), so email and in-app notification always stay in sync and
# neither can be duplicated by calling this from multiple places. The two
# "Apply" submission views call it once more, directly, right after
# creating the Application (there is no "old status" for a brand new
# application, so they pass old_status=None).
# ---------------------------------------------------------------------------

# Statuses that get a student-facing email. Applied is included here (not
# just a create-time side effect) so record_status_change() also emails a
# student if an application is ever explicitly reset back to Applied.
_STATUS_EMAIL_STATUSES = {
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_UNDER_REVIEW,
    APPLICATION_STATUS_SHORTLISTED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_SELECTED,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_REJECTED,
}

_STATUS_EMAIL_SUBJECTS = {
    APPLICATION_STATUS_APPLIED: "Application Submitted — {job_title} at {company_name}",
    APPLICATION_STATUS_UNDER_REVIEW: "Application Update — Your Application is Under Review",
    APPLICATION_STATUS_SHORTLISTED: "Congratulations — Your Application Has Been Shortlisted",
    APPLICATION_STATUS_INTERVIEW: "Interview Update — {job_title} at {company_name}",
    APPLICATION_STATUS_SELECTED: "Congratulations — You Have Been Selected",
    APPLICATION_STATUS_HIRED: "Congratulations — You Have Been Hired",
    APPLICATION_STATUS_REJECTED: "Application Update — {job_title} at {company_name}",
}


def _status_email_body(application, new_status, job):
    """Status-specific paragraphs for the shared application_status_email.txt
    template. Only ever states what is actually true of `application` -
    never invents an interview time/link, an offer, a joining date, etc.
    that the database doesn't hold (spec sections 5-8, 25)."""
    job_title = job.title
    company_name = job.company.name

    if new_status == APPLICATION_STATUS_APPLIED:
        return [
            "Your application has been successfully submitted.",
            f"We have received your application for the {job_title} position at {company_name}, "
            f"submitted on {application.applied_at:%d %b %Y}.",
        ]

    if new_status == APPLICATION_STATUS_UNDER_REVIEW:
        return [
            "Your application has been moved to the Under Review stage.",
            "Our hiring team is currently reviewing your profile and application. We will "
            "update you as soon as a decision is made.",
        ]

    if new_status == APPLICATION_STATUS_SHORTLISTED:
        return [
            f"Congratulations! Your application for the {job_title} position at {company_name} "
            "has been shortlisted by the hiring team.",
            "The next steps will be communicated to you directly by the company.",
        ]

    if new_status == APPLICATION_STATUS_INTERVIEW:
        paragraphs = [
            f"Congratulations! Your application for the {job_title} position at {company_name} "
            "has reached the interview stage.",
        ]
        interview = application.interviews.order_by("-created_at").first()
        if interview:
            detail = (
                f"Interview details: {interview.get_interview_type_display()} interview "
                f"scheduled for {interview.scheduled_at:%d %b %Y, %H:%M} (IST)."
            )
            if interview.location:
                detail += f" Location: {interview.location}."
            if interview.meeting_link:
                detail += f" Meeting link: {interview.meeting_link}."
            paragraphs.append(detail)
        else:
            paragraphs.append(
                "The company will contact you shortly with the interview date, time, and other details."
            )
        return paragraphs

    if new_status == APPLICATION_STATUS_SELECTED:
        return [
            "Congratulations! We are pleased to inform you that you have been selected for "
            f"the {job_title} position at {company_name}.",
            "The hiring team will be in touch with you regarding the next steps.",
        ]

    if new_status == APPLICATION_STATUS_HIRED:
        return [
            f"Congratulations! You have been hired for the {job_title} position at {company_name}.",
            "We are delighted to let you know that your application has been marked as Hired "
            "by the hiring team. We wish you great success in your new opportunity.",
        ]

    if new_status == APPLICATION_STATUS_REJECTED:
        return [
            f"Thank you for your interest in the {job_title} position at {company_name}. After "
            "careful consideration, the hiring team has decided not to move forward with your "
            "application at this time.",
            "Please don't be discouraged. There are many opportunities available on NammaCareer, "
            "and we encourage you to continue exploring roles that match your skills and experience.",
        ]

    return None


def send_application_status_email(application, old_status, new_status):
    """Send `application`'s candidate the status-specific email for
    `new_status` (spec sections 3-9, 14-18, 25). A no-op - and never an
    email - when the status hasn't actually changed (old_status ==
    new_status), so repeated saves/double-clicks/bulk re-runs never send a
    duplicate email (spec sections 10, 21).

    Never raises: any failure building or sending the email is logged and
    swallowed so it can never break or roll back the caller's status update
    (spec section 19). Returns True once the email is actually sent, False
    if it was skipped (no-op transition, unsupported status, no usable
    recipient email) or if sending failed.
    """
    if old_status == new_status:
        return False
    if new_status not in _STATUS_EMAIL_STATUSES:
        return False

    recipient_email = application.applicant.email or application.email
    if not recipient_email:
        logger.warning(
            "Skipping application status email: application %s has no usable recipient email "
            "(status=%s).",
            application.pk, new_status,
        )
        return False

    job = application.job
    body_paragraphs = _status_email_body(application, new_status, job)
    if not body_paragraphs:
        return False

    context = {
        "candidate_name": application.full_name(),
        "job_title": job.title,
        "company_name": job.company.name,
        "status_display": application.get_status_display(),
        "body_paragraphs": body_paragraphs,
        "cta_text": None,
        "cta_url": None,
    }
    if new_status == APPLICATION_STATUS_REJECTED:
        context["cta_text"] = "Explore More Jobs"
        context["cta_url"] = reverse("jobs:list")

    subject = _STATUS_EMAIL_SUBJECTS[new_status].format(job_title=job.title, company_name=job.company.name)
    message = render_to_string("emails/application_status_email.txt", context)

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send application status email for application %s (status=%s) to %s.",
            application.pk, new_status, recipient_email,
        )
        return False

    logger.info(
        "Sent application status email for application %s (status=%s) to %s.",
        application.pk, new_status, recipient_email,
    )
    return True

"""Side effects triggered when a job is published: notify company followers
and matching job alerts (spec sections 25, 38, 59) - deterministic, no AI.
"""
from core.constants import NOTIFICATION_TYPE_COMPANY, NOTIFICATION_TYPE_JOB
from notifications.services import create_notification


def notify_job_published(job):
    from accounts.models import JobAlert
    from companies.models import CompanyFollow

    for follow in CompanyFollow.objects.filter(company=job.company).select_related("user"):
        create_notification(
            follow.user,
            NOTIFICATION_TYPE_COMPANY,
            f"{job.company.name} posted a new job",
            job.title,
            job=job,
            company=job.company,
        )

    for alert in JobAlert.objects.filter(is_active=True).select_related("user"):
        if alert.matches(job):
            create_notification(
                alert.user,
                NOTIFICATION_TYPE_JOB,
                f"New job matches your alert \"{alert.name}\"",
                job.title,
                job=job,
            )

"""Side effects triggered when a job is published: notify company followers
and matching job alerts (spec sections 25, 38, 59) - deterministic, no AI.
"""
from datetime import timedelta

from django.utils import timezone

from core.constants import JOB_VIEW_DEDUP_HOURS, NOTIFICATION_TYPE_COMPANY, NOTIFICATION_TYPE_JOB
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


def record_job_view(job, request):
    """Real, deduplicated job-view tracking (spec section 7). One authenticated
    user, or one anonymous session, counts as at most one unique view per job
    within JOB_VIEW_DEDUP_HOURS - repeated refreshes don't inflate the count.
    Job.views_count is only bumped when a genuinely new JobView is recorded,
    so existing templates reading it stay accurate without changes. The job
    owner viewing their own listing is never counted.
    """
    from jobs.models import Job, JobView

    if request.user.is_authenticated and job.employer_id == request.user.id:
        return

    cutoff = timezone.now() - timedelta(hours=JOB_VIEW_DEDUP_HOURS)
    if request.user.is_authenticated:
        already_recent = JobView.objects.filter(job=job, viewer=request.user, viewed_at__gte=cutoff).exists()
        viewer, session_key = request.user, ""
    else:
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key or ""
        already_recent = JobView.objects.filter(
            job=job, viewer__isnull=True, session_key=session_key, viewed_at__gte=cutoff
        ).exists()
        viewer = None

    if already_recent:
        return

    JobView.objects.create(job=job, viewer=viewer, session_key=session_key)
    Job.objects.filter(pk=job.pk).update(views_count=job.views_count + 1)

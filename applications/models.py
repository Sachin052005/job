from django.conf import settings
from django.db import models

from core.constants import (
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_BADGE_CLASS,
    APPLICATION_STATUS_CHOICES,
    APPLIED_VIA_CHOICES,
    APPLIED_VIA_MANUAL,
    ATS_STATUS_CHOICES,
    ATS_STATUS_PENDING,
    INTERVIEW_RESULT_CHOICES,
    INTERVIEW_RESULT_PENDING,
    INTERVIEW_TYPE_CHOICES,
)
from core.utils import unique_upload_path
from core.validators import validate_profile_url, validate_resume_file


class Application(models.Model):
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )

    # Snapshot of the applicant's information at submission time (spec sections
    # 14/15/17) - captured on the Application itself rather than only living on
    # the mutable Profile, so HR sees what was true when the candidate applied.
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=120, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    current_title = models.CharField(max_length=150, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    education_summary = models.CharField(max_length=300, blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    linkedin_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    github_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    portfolio_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])

    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to=unique_upload_path("application_resumes"), validators=[validate_resume_file])
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, default=APPLICATION_STATUS_APPLIED)
    applied_via = models.CharField(max_length=20, choices=APPLIED_VIA_CHOICES, default=APPLIED_VIA_MANUAL)

    # Deterministic skill-match snapshot (spec sections 6/13), calculated by
    # services.skill_match_service.calculate_skill_match() at submission time
    # and frozen here - the candidate's profile/resume skills can change
    # later, but HR must keep seeing the match that existed when they applied.
    match_percentage = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Null means the job had no required skills to match against."
    )
    matched_skills = models.JSONField(default=list, blank=True)
    unmatched_skills = models.JSONField(default=list, blank=True)
    student_skills_snapshot = models.JSONField(default=list, blank=True)
    job_skills_snapshot = models.JSONField(default=list, blank=True)

    # Full ATS analysis (resumes.services.job_match), computed once right
    # after the application is created. Additive to match_percentage/
    # matched_skills/unmatched_skills above (the simple required-skill-only
    # snapshot already shown by _skill_match.html) - this holds the fuller
    # multi-component breakdown (preferred skills, experience, education,
    # keyword coverage, project relevance, ...) for the recruiter ATS
    # dashboard. Never blocks application submission: on parser/analysis
    # failure ats_status becomes FAILED with ats_error logged internally,
    # the application itself remains valid (spec: ATS must not break
    # applications).
    ats_status = models.CharField(max_length=12, choices=ATS_STATUS_CHOICES, default=ATS_STATUS_PENDING)
    ats_score = models.PositiveSmallIntegerField(null=True, blank=True)
    ats_breakdown = models.JSONField(default=dict, blank=True)
    ats_error = models.TextField(blank=True)
    ats_processed_at = models.DateTimeField(null=True, blank=True)

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "applicant"], name="unique_application_per_job"),
        ]

    def __str__(self):
        return f"{self.applicant} -> {self.job}"

    def badge_class(self):
        return APPLICATION_STATUS_BADGE_CLASS.get(self.status, "secondary")

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.applicant.get_username()

    def apply_skill_match(self, match_result):
        """Freeze a services.skill_match_service.calculate_skill_match() result onto this application."""
        self.match_percentage = match_result["percentage"]
        self.matched_skills = match_result["matched_skills"]
        self.unmatched_skills = match_result["unmatched_skills"]
        self.student_skills_snapshot = match_result["candidate_skills"]
        self.job_skills_snapshot = match_result["job_skills"]

    def has_skill_match(self):
        return self.match_percentage is not None

    @property
    def match_snapshot(self):
        """Same shape as services.skill_match_service.calculate_skill_match() so
        templates can render either a live match or this frozen one identically."""
        return {
            "percentage": self.match_percentage,
            "matched_skills": self.matched_skills or [],
            "unmatched_skills": self.unmatched_skills or [],
            "candidate_skills": self.student_skills_snapshot or [],
            "job_skills": self.job_skills_snapshot or [],
        }

    def record_status_change(self, new_status, changed_by=None, note=""):
        """The single choke point for every status change (HR's
        update-status view, the manual admin panel's status edit, its bulk
        actions) - so the student's in-app notification and status email
        are each triggered exactly once per real transition, from exactly
        one place, regardless of who changed it. `changed_by` (HR or admin)
        is never the notification/email recipient.

        A no-op (returns changed=False, no notification/email/history row)
        if `new_status` equals the current status, so callers can call this
        unconditionally - including on a double-submit or a repeat bulk
        action - without ever sending a duplicate email.

        Returns a dict describing what happened: {"changed": bool,
        "email_sent": bool}, so callers (e.g. the HR status-update view) can
        show an accurate confirmation message without duplicating any of
        this logic.
        """
        old_status = self.status
        if old_status == new_status:
            return {"changed": False, "email_sent": False}
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        ApplicationStatusHistory.objects.create(
            application=self, old_status=old_status, new_status=new_status, changed_by=changed_by, note=note
        )
        from notifications.services import notify_application_status_change, send_application_status_email

        notify_application_status_change(self, old_status, new_status)
        email_sent = send_application_status_email(self, old_status, new_status)

        from activity.services import record_application_status_activity

        record_application_status_activity(self, new_status, changed_by)

        return {"changed": True, "email_sent": email_sent}


class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, blank=True)
    new_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.application_id}: {self.old_status} -> {self.new_status}"


class Interview(models.Model):
    """One scheduled interview for an Application. A single application may
    go through more than one round, so this is a related set, not a
    one-to-one - the pipeline status itself stays on Application.status
    (spec: reuse the existing status system, don't duplicate it)."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="interviews")
    interview_type = models.CharField(max_length=20, choices=INTERVIEW_TYPE_CHOICES)
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, help_text="Physical address, if onsite")
    meeting_link = models.URLField(max_length=500, blank=True, help_text="Video call link, if remote")
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    notes = models.TextField(blank=True, help_text="Recruiter-only prep notes, shared with the interviewer")
    feedback = models.TextField(blank=True, help_text="Recruiter-only post-interview feedback")
    result = models.CharField(max_length=10, choices=INTERVIEW_RESULT_CHOICES, default=INTERVIEW_RESULT_PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self):
        return f"{self.get_interview_type_display()} interview for {self.application_id} on {self.scheduled_at:%Y-%m-%d}"


class RecruiterNote(models.Model):
    """A private note an authorized recruiter/company user leaves on an
    application. Never visible to the candidate (spec: recruiter notes are
    private)."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="recruiter_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by {self.author} on application {self.application_id}"



from django.conf import settings
from django.db import models

from core.constants import (
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_BADGE_CLASS,
    APPLICATION_STATUS_CHOICES,
    APPLIED_VIA_CHOICES,
    APPLIED_VIA_MANUAL,
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

    def record_status_change(self, new_status, changed_by=None):
        old_status = self.status
        if old_status == new_status:
            return
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        ApplicationStatusHistory.objects.create(
            application=self, old_status=old_status, new_status=new_status, changed_by=changed_by
        )
        # The single choke point for every status change (HR's update-status
        # view, the manual admin panel's status edit, its bulk actions) - so
        # the student notification is triggered exactly once per real
        # transition, from exactly one place, regardless of who changed it.
        # `changed_by` (HR or admin) is never the notification recipient.
        from notifications.services import notify_application_status_change

        notify_application_status_change(self, old_status, new_status)


class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="status_history")
    old_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, blank=True)
    new_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.application_id}: {self.old_status} -> {self.new_status}"


class ScreeningAnswer(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="screening_answers")
    question = models.ForeignKey("jobs.ScreeningQuestion", on_delete=models.CASCADE, related_name="answers")
    answer_text = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["application", "question"], name="unique_answer_per_question"),
        ]

    def __str__(self):
        return f"Answer for {self.question_id} on application {self.application_id}"

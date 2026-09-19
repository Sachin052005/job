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
from core.validators import validate_resume_file


class Application(models.Model):
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to=unique_upload_path("application_resumes"), validators=[validate_resume_file])
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, default=APPLICATION_STATUS_APPLIED)
    applied_via = models.CharField(max_length=20, choices=APPLIED_VIA_CHOICES, default=APPLIED_VIA_MANUAL)
    match_snapshot = models.JSONField(
        blank=True,
        null=True,
        help_text="Compact ATS match analysis captured when the application was submitted/analyzed.",
    )
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

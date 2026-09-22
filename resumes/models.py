from django.conf import settings
from django.db import models

from core.utils import unique_upload_path
from core.validators import validate_resume_file


class Resume(models.Model):
    """One named, uploaded resume version belonging to a student (spec
    section 65). Independent of accounts.Profile.resume (the single resume
    used by Easy Apply, unchanged) - this is the versioned set a student
    manages and runs ATS scans against, e.g. "Python Developer Resume",
    "Fresher Resume"."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=150, help_text="e.g. Python Developer Resume")
    file = models.FileField(upload_to=unique_upload_path("resume_versions"), validators=[validate_resume_file])
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "-updated_at"]
        indexes = [models.Index(fields=["student"])]

    def __str__(self):
        return f"{self.title} ({self.student})"

    def latest_scan(self):
        return self.scans.order_by("-created_at").first()


class ResumeScan(models.Model):
    """One NammaCareer Resume Health / ATS Compatibility analysis run against
    a Resume (spec sections 56-64). Stored (not recomputed on every view) so
    the student can revisit a past result. `score_breakdown` holds the
    category sub-scores (ATS Compatibility, Content Quality, Skills Coverage,
    Impact, Formatting, Student Readiness); `extracted_data` holds what the
    parser found (contact info, sections, detected skills, etc.)."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="scans")
    score = models.PositiveSmallIntegerField(help_text="Overall NammaCareer Resume Health score, 0-100")
    score_breakdown = models.JSONField(default=dict, blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["resume", "-created_at"])]

    def __str__(self):
        return f"Scan of {self.resume} - {self.score}/100"


class ResumeJobMatch(models.Model):
    """One resume-vs-job-description compatibility analysis (spec section
    61). `job` is set when matched against an actual NammaCareer job posting;
    `job_description_text` holds the pasted text when the student supplies a
    JD directly instead."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="job_matches")
    job = models.ForeignKey("jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    job_description_text = models.TextField(
        blank=True, help_text="Pasted job description text, when not matched against an actual Job posting."
    )
    compatibility_score = models.PositiveSmallIntegerField()
    matched_skills = models.JSONField(default=list, blank=True)
    missing_skills = models.JSONField(default=list, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["resume", "-created_at"])]

    def __str__(self):
        target = self.job.title if self.job else "a pasted job description"
        return f"Match: {self.resume} vs {target} - {self.compatibility_score}%"

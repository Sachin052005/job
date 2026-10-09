import hashlib

from django.conf import settings
from django.db import models

from core.constants import (
    ISSUE_PRIORITY_CHOICES,
    PARSE_STATUS_CHOICES,
    PARSE_STATUS_PENDING,
    PARSER_VERSION,
)
from core.utils import unique_upload_path
from core.validators import validate_resume_file

ISSUE_STATUS_OPEN = "open"
ISSUE_STATUS_FIXED = "fixed"
ISSUE_STATUS_IGNORED = "ignored"

ISSUE_STATUS_CHOICES = [
    (ISSUE_STATUS_OPEN, "Open"),
    (ISSUE_STATUS_FIXED, "Fixed"),
    (ISSUE_STATUS_IGNORED, "Ignored"),
]


class Resume(models.Model):
    """One named, uploaded resume version belonging to a student (spec
    section 65). Independent of accounts.Profile.resume (the single resume
    used by Easy Apply, unchanged) - this is the versioned set a student
    manages and runs ATS scans against, e.g. "Python Developer Resume",
    "Fresher Resume".

    parsed_text/parsed_data are a cache of the raw parser output (ATS spec
    parts 7/38): reused by every "Analyze"/job-match run against this
    version instead of re-parsing the file, and invalidated (parse_status
    reset to PENDING) only when the file actually changes - see
    resumes.services.parser.ensure_parsed().
    """

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=150, help_text="e.g. Python Developer Resume")
    file = models.FileField(upload_to=unique_upload_path("resume_versions"), validators=[validate_resume_file])
    is_primary = models.BooleanField(default=False)

    file_hash = models.CharField(max_length=64, blank=True)
    parse_status = models.CharField(max_length=10, choices=PARSE_STATUS_CHOICES, default=PARSE_STATUS_PENDING)
    parse_error = models.TextField(blank=True)
    parsed_text = models.TextField(blank=True)
    parsed_data = models.JSONField(default=dict, blank=True)
    parser_version = models.CharField(max_length=10, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "-updated_at"]
        indexes = [models.Index(fields=["student"])]

    def __str__(self):
        return f"{self.title} ({self.student})"

    def latest_scan(self):
        return self.scans.order_by("-created_at").first()

    def compute_file_hash(self):
        self.file.seek(0)
        digest = hashlib.sha256(self.file.read()).hexdigest()
        self.file.seek(0)
        return digest

    def needs_reparse(self):
        if self.parse_status != "parsed":
            return True
        if self.parser_version != PARSER_VERSION:
            return True
        try:
            return self.compute_file_hash() != self.file_hash
        except (FileNotFoundError, ValueError):
            return True


class ResumeScan(models.Model):
    """One TalentPanda Resume Health / ATS Compatibility analysis run against
    a Resume (spec sections 56-64). Stored (not recomputed on every view) so
    the student can revisit a past result. `score_breakdown` holds the
    category sub-scores (ATS Compatibility, Content Quality, Skills Coverage,
    Impact, Formatting, Student Readiness); `extracted_data` holds what the
    parser found (contact info, sections, detected skills, etc.)."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="scans")
    score = models.PositiveSmallIntegerField(help_text="Overall TalentPanda Resume Health score, 0-100")
    score_breakdown = models.JSONField(default=dict, blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    analyzer_version = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["resume", "-created_at"])]

    def __str__(self):
        return f"Scan of {self.resume} - {self.score}/100"


class ResumeJobMatch(models.Model):
    """One resume-vs-job-description compatibility analysis (spec section
    61). `job` is set when matched against an actual TalentPanda job posting;
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


class ATSIssue(models.Model):
    """One individual, actionable finding from a ResumeScan (Fix Center /
    red-underline system). Distinct from ResumeScan.issues (a plain JSON
    snapshot of what a given scan found) because a single issue needs its
    own mutable state - a student can mark it FIXED or IGNORED, and that
    state should be visible in the Fix Center independent of re-scanning.
    `start_position`/`end_position` index into resume.parsed_text when the
    issue is anchored to a specific quoted span (e.g. a weak bullet) so the
    resume preview can highlight exactly that text; both are null for
    document-level findings (e.g. "multi-column layout detected")."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="ats_issues")
    scan = models.ForeignKey(ResumeScan, on_delete=models.CASCADE, related_name="ats_issues")
    category = models.CharField(max_length=30)
    severity = models.CharField(max_length=10, choices=ISSUE_PRIORITY_CHOICES)
    section = models.CharField(max_length=30, blank=True)
    text = models.TextField(blank=True, help_text="The affected quoted text, if this issue is anchored to a span.")
    start_position = models.PositiveIntegerField(null=True, blank=True)
    end_position = models.PositiveIntegerField(null=True, blank=True)
    page = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.CharField(max_length=300)
    suggestion = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ISSUE_STATUS_CHOICES, default=ISSUE_STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["severity", "-created_at"]
        indexes = [models.Index(fields=["resume", "status"])]

    def __str__(self):
        return f"[{self.severity}] {self.message}"

from django.conf import settings
from django.db import models

from core.constants import (
    PROFILE_VIEW_SOURCE_CHOICES,
    PROFILE_VIEW_SOURCE_DIRECT,
    STUDENT_ACTIVITY_EVENT_CHOICES,
)


class StudentSearchAppearance(models.Model):
    """One recruiter candidate-search result appearance for a student (spec
    section 10). Deduplicated per (student, recruiter) within
    core.constants.SEARCH_APPEARANCE_DEDUP_HOURS by the write path in
    activity.services - repeated searches/refreshes within the window do not
    create a new row."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="search_appearances"
    )
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    search_query = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["recruiter", "student"]),
        ]

    def __str__(self):
        return f"{self.student} appeared in a search by {self.recruiter}"


class StudentProfileView(models.Model):
    """One recruiter viewing of a student's profile (spec section 11).

    `source` records what led the recruiter there (candidate search vs. an
    application vs. a direct link), so the student-facing notification/
    timeline can say where the interaction came from (spec section 39).
    Deduplicated per (student, recruiter) within
    core.constants.PROFILE_VIEW_DEDUP_HOURS by activity.services - a recruiter
    reloading the same profile repeatedly does not create a new row.
    """

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_views")
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    source = models.CharField(max_length=20, choices=PROFILE_VIEW_SOURCE_CHOICES, default=PROFILE_VIEW_SOURCE_DIRECT)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["student", "-viewed_at"]),
            models.Index(fields=["recruiter", "student"]),
        ]

    def __str__(self):
        return f"{self.recruiter} viewed {self.student}'s profile"


class StudentActivity(models.Model):
    """Canonical recruiter-action/activity log for a student (spec section
    13). One row per meaningful event - drives the student performance
    timeline (spec section 38), the "Recruiter Actions" counter (spec section
    35), and student notifications (via notifications.services). Deliberately
    one reusable model rather than many unrelated event tables (spec section
    13's own guidance).
    """

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    event_type = models.CharField(max_length=30, choices=STUDENT_ACTIVITY_EVENT_CHOICES)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    application = models.ForeignKey(
        "applications.Application", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    job = models.ForeignKey("jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "student activities"
        indexes = [
            models.Index(fields=["student", "-created_at"]),
            models.Index(fields=["student", "event_type"]),
            models.Index(fields=["company", "event_type"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.student}"

    def actor_label(self):
        """'Rahul from ABC Technologies' style label (spec section 39), degrading
        gracefully when the recruiter's name or the company isn't available."""
        recruiter_name = (self.recruiter.first_name or "").strip() if self.recruiter else ""
        company_name = self.company.name if self.company else ""
        if recruiter_name and company_name:
            return f"{recruiter_name} from {company_name}"
        if company_name:
            return f"A recruiter from {company_name}"
        if recruiter_name:
            return recruiter_name
        return "A recruiter"

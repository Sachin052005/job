from functools import partial

from django.conf import settings
from django.db import models

from core.constants import EASY_APPLY_REQUIRED_FIELDS, PROFILE_COMPLETENESS_SECTIONS, ROLE_CHOICES, ROLE_JOB_SEEKER
from core.utils import unique_upload_path
from core.validators import validate_image_file, validate_profile_url, validate_resume_file


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_JOB_SEEKER)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=120, blank=True)
    headline = models.CharField(max_length=150, blank=True)
    summary = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    experience_years = models.PositiveSmallIntegerField(default=0)
    photo = models.ImageField(
        upload_to=unique_upload_path("profile_photos"),
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    resume = models.FileField(
        upload_to=unique_upload_path("resumes"),
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    linkedin_url = models.URLField(
        max_length=300, blank=True, validators=[partial(validate_profile_url, kind="linkedin")]
    )
    github_url = models.URLField(
        max_length=300, blank=True, validators=[partial(validate_profile_url, kind="github")]
    )
    portfolio_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    website_url = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def completion_percent(self):
        total = len(PROFILE_COMPLETENESS_SECTIONS)
        if total == 0:
            return 100
        filled = sum(1 for field, _label in PROFILE_COMPLETENESS_SECTIONS if getattr(self, field, ""))
        return int((filled / total) * 100)

    def missing_sections(self):
        """Labels of recommended profile sections that are still empty."""
        return [label for field, label in PROFILE_COMPLETENESS_SECTIONS if not getattr(self, field, "")]

    def is_easy_apply_ready(self):
        """Hard gate for Easy Apply: the fields actually needed to build an application."""
        return all(getattr(self, field, "") for field in EASY_APPLY_REQUIRED_FIELDS)

    def missing_easy_apply_fields(self):
        labels = dict(PROFILE_COMPLETENESS_SECTIONS)
        return [labels.get(field, field) for field in EASY_APPLY_REQUIRED_FIELDS if not getattr(self, field, "")]

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.constants import (
    EMPLOYMENT_TYPE_CHOICES,
    JOB_STATUS_BADGE_CLASS,
    JOB_STATUS_CHOICES,
    JOB_STATUS_DRAFT,
    JOB_STATUS_PUBLISHED,
)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Job(models.Model):
    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="jobs")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=150)
    description = models.TextField()
    responsibilities = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated skills")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="full_time")
    experience_min = models.PositiveSmallIntegerField(default=0)
    experience_max = models.PositiveSmallIntegerField(default=0)
    salary_min = models.PositiveIntegerField(blank=True, null=True)
    salary_max = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default=JOB_STATUS_DRAFT)
    application_deadline = models.DateField(blank=True, null=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["location"]),
            models.Index(fields=["title"]),
        ]

    def save(self, *args, **kwargs):
        if self.status == JOB_STATUS_PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("jobs:detail", kwargs={"pk": self.pk})

    def skills_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def is_open(self):
        if self.status != JOB_STATUS_PUBLISHED:
            return False
        if self.application_deadline and self.application_deadline < timezone.now().date():
            return False
        return True

    def application_count(self):
        return self.applications.count()

    def badge_class(self):
        return JOB_STATUS_BADGE_CLASS.get(self.status, "secondary")

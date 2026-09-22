from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.constants import (
    APPLICATION_METHOD_APPLY,
    APPLICATION_METHOD_BOTH,
    APPLICATION_METHOD_CHOICES,
    APPLICATION_METHOD_EASY_APPLY,
    EDUCATION_LEVEL_CHOICES,
    EMPLOYMENT_TYPE_CHOICES,
    JOB_BADGE_CHOICES,
    JOB_STATUS_BADGE_CLASS,
    JOB_STATUS_CHOICES,
    JOB_STATUS_DRAFT,
    JOB_STATUS_PUBLISHED,
    WORK_MODE_CHOICES,
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
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, blank=True)
    experience_min = models.PositiveSmallIntegerField(default=0)
    experience_max = models.PositiveSmallIntegerField(default=0)
    education_required = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES, blank=True)
    salary_min = models.PositiveIntegerField(blank=True, null=True)
    salary_max = models.PositiveIntegerField(blank=True, null=True)
    benefits = models.TextField(blank=True)
    highlights = models.TextField(blank=True)
    badges = models.CharField(
        max_length=300, blank=True, help_text="Comma-separated badge keys, e.g. urgent_hiring,remote"
    )
    application_method = models.CharField(
        max_length=20, choices=APPLICATION_METHOD_CHOICES, default=APPLICATION_METHOD_BOTH
    )
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

    def badges_list(self):
        return [b.strip() for b in self.badges.split(",") if b.strip()]

    def badge_labels(self):
        labels = dict(JOB_BADGE_CHOICES)
        return [labels.get(key, key) for key in self.badges_list()]

    def allows_easy_apply(self):
        return self.application_method in (APPLICATION_METHOD_EASY_APPLY, APPLICATION_METHOD_BOTH)

    def allows_apply(self):
        return self.application_method in (APPLICATION_METHOD_APPLY, APPLICATION_METHOD_BOTH)


class ScreeningQuestion(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="screening_questions")
    question = models.CharField(max_length=300)
    is_required = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.question

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
    """Legacy flat job category - superseded by JobDomain/JobSubdomain (spec
    sections 17-21). Kept only until Phase 6 (domains wiring) migrates every
    remaining usage (job alerts, filters, forms) off it and removes it and
    Job.category in one clean follow-up migration - not a permanent duplicate
    taxonomy alongside JobDomain/JobSubdomain."""

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


class JobDomain(models.Model):
    """Top-level job domain (spec section 17) - exactly IT / Non-IT / Medical
    Coding, seeded by a data migration. Not user-creatable beyond that set in
    the current spec, but modeled as a normal table (not a hardcoded choices
    list) so display_order/is_active stay data-driven."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class JobSubdomain(models.Model):
    """Subdomain within a JobDomain (spec sections 18-20) - the subdomain
    choices offered when creating/editing a job depend on the selected
    JobDomain (spec section 22)."""

    domain = models.ForeignKey(JobDomain, on_delete=models.CASCADE, related_name="subdomains")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["domain", "slug"], name="unique_subdomain_slug_per_domain"),
            models.UniqueConstraint(fields=["domain", "name"], name="unique_subdomain_name_per_domain"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.domain.name} / {self.name}"


class Job(models.Model):
    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="jobs")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    # domain/subdomain replace `category` (spec sections 17-22). Nullable at
    # the DB level only to keep the transition migration non-destructive;
    # JobForm requires both for every new/edited job going forward, and the
    # Phase 3 data migration backfills every pre-existing job.
    domain = models.ForeignKey(
        JobDomain, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    subdomain = models.ForeignKey(
        JobSubdomain, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=150)
    description = models.TextField()
    responsibilities = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text="Comma-separated required skills")
    preferred_skills = models.CharField(
        max_length=500, blank=True, help_text="Comma-separated preferred (nice-to-have) skills"
    )
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

    def preferred_skills_list(self):
        return [s.strip() for s in self.preferred_skills.split(",") if s.strip()]

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


class JobView(models.Model):
    """One real job-detail view (spec section 7).

    Deduplicated per (job, viewer) for authenticated users and per
    (job, session_key) for anonymous visitors within
    core.constants.JOB_VIEW_DEDUP_HOURS - see jobs.views.JobDetailView, the
    single write path for this model. Job.views_count stays a denormalized
    counter incremented only when a genuinely new JobView is recorded, so
    existing templates reading it keep working unchanged.
    """

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="view_events")
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    session_key = models.CharField(max_length=40, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["job", "viewer"]),
            models.Index(fields=["job", "session_key"]),
        ]

    def __str__(self):
        return f"View of job {self.job_id} at {self.viewed_at}"

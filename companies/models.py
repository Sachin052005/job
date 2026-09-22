from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.constants import (
    COMPANY_TYPE_CHOICES,
    EMPLOYMENT_TYPE_CHOICES,
    EXPERIENCE_LEVEL_CHOICES,
    VERIFICATION_STATUS_CHOICES,
    VERIFICATION_UNVERIFIED,
)
from core.utils import unique_upload_path
from core.validators import validate_image_file, validate_profile_url, validate_resume_file


class Company(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company"
    )
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    legal_name = models.CharField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=120, blank=True)
    sub_industry = models.CharField(max_length=120, blank=True)
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, help_text="e.g. 11-50 employees")
    logo = models.ImageField(
        upload_to=unique_upload_path("company_logos"),
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    cover_image = models.ImageField(
        upload_to=unique_upload_path("company_covers"),
        blank=True,
        null=True,
        validators=[validate_image_file],
    )

    mission = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    official_email = models.EmailField(blank=True)
    official_phone = models.CharField(max_length=30, blank=True)

    products = models.TextField(blank=True)
    services_offered = models.TextField(blank=True)
    technologies = models.CharField(max_length=500, blank=True, help_text="Comma-separated technologies")
    culture = models.TextField(blank=True)
    work_environment = models.TextField(blank=True)
    benefits = models.TextField(blank=True)

    business_proof = models.FileField(
        upload_to=unique_upload_path("company_verification"),
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    official_domain = models.CharField(max_length=150, blank=True)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default=VERIFICATION_UNVERIFIED
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Company.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def active_job_count(self):
        return self.jobs.filter(status="published").count()

    def technologies_list(self):
        return [t.strip() for t in self.technologies.split(",") if t.strip()]

    def active_reviews(self):
        return self.reviews.filter(is_active=True).select_related("applicant")

    def review_count(self):
        return self.active_reviews().count()

    def review_average(self):
        from django.db.models import Avg

        return self.active_reviews().aggregate(avg=Avg("rating"))["avg"]

    def review_breakdown(self):
        """Star -> {count, percent}, computed from actual reviews only (spec section 19)."""
        from django.db.models import Count

        total = self.review_count()
        rows = self.active_reviews().values("rating").annotate(count=Count("id"))
        counts = {row["rating"]: row["count"] for row in rows}
        breakdown = []
        for star in range(5, 0, -1):
            count = counts.get(star, 0)
            percent = round((count / total) * 100) if total else 0
            breakdown.append({"star": star, "count": count, "percent": percent})
        return breakdown

    def follower_count(self):
        return self.followers.count()


class CompanyFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_companies")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="followers")
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-followed_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="unique_company_follow"),
        ]

    def __str__(self):
        return f"{self.user} follows {self.company}"


class CompanyOffice(models.Model):
    """A company branch/location (spec section 6). Reused as the single
    Company-locations model - a company can have any number of these."""

    OFFICE_TYPE_CHOICES = [
        ("headquarters", "Headquarters"),
        ("branch", "Branch"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="offices")
    name = models.CharField(max_length=150, blank=True, help_text="e.g. Chennai Office")
    office_type = models.CharField(max_length=20, choices=OFFICE_TYPE_CHOICES, default="branch")
    country = models.CharField(max_length=100, blank=True, default="India")
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    is_headquarters = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_headquarters", "city"]

    def __str__(self):
        return self.name or f"{self.company.name} - {self.city or self.area or self.get_office_type_display()}"


class CompanySalary(models.Model):
    """HR-entered salary information for a role (spec section 4) - never
    auto-generated, only what HR actually enters."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="salaries")
    role = models.CharField(max_length=150)
    salary_range = models.CharField(max_length=100, help_text="e.g. ₹4 LPA - ₹8 LPA")
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    location = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role"]
        indexes = [models.Index(fields=["company"])]

    def __str__(self):
        return f"{self.role} - {self.company.name}"


class CompanyProductService(models.Model):
    """A single product or service a company offers (spec section 7) - a proper
    related model instead of one free-text field, so each item is structured."""

    TYPE_PRODUCT = "product"
    TYPE_SERVICE = "service"
    TYPE_CHOICES = [
        (TYPE_PRODUCT, "Product"),
        (TYPE_SERVICE, "Service"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products_services")
    item_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_PRODUCT)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    link = models.URLField(max_length=300, blank=True, validators=[validate_profile_url])
    image = models.ImageField(
        upload_to=unique_upload_path("company_products"), blank=True, null=True, validators=[validate_image_file]
    )
    order = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        indexes = [models.Index(fields=["company"])]

    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"


class CompanyReview(models.Model):
    """A verified student review of a company (spec sections 9-21).

    Eligibility is enforced entirely server-side (see companies.views) and is
    anchored to a specific hired Application - not to "applied"/"shortlisted"/
    "interview" states - so `application` doubles as the eligibility record.
    One review per (company, applicant): a student reviews the company once,
    regardless of how many roles they were hired for there.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="reviews")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_reviews"
    )
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="company_review"
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField()
    image = models.ImageField(
        upload_to=unique_upload_path("company_review_images"), blank=True, null=True, validators=[validate_image_file]
    )
    is_active = models.BooleanField(default=True, help_text="HR can hide a review without editing its content.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "is_active"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "applicant"], name="unique_review_per_student_per_company"),
        ]

    def __str__(self):
        return f"{self.applicant} -> {self.company} ({self.rating}★)"

    def reviewer_display_name(self):
        """Privacy-safe display name (spec section 17) - first name only, falling back to username."""
        first_name = (self.applicant.first_name or "").strip()
        return first_name or self.applicant.get_username()

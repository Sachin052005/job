from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.utils import unique_upload_path
from core.validators import validate_image_file


class Company(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company"
    )
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    industry = models.CharField(max_length=120, blank=True)
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

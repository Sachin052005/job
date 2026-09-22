from django.conf import settings
from django.db import models
from django.urls import reverse

from core.constants import NOTIFICATION_TYPE_CHOICES, NOTIFICATION_TYPE_SYSTEM


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default=NOTIFICATION_TYPE_SYSTEM)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    job = models.ForeignKey("jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    application = models.ForeignKey(
        "applications.Application", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    company = models.ForeignKey("companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.application_id:
            return reverse("applications:detail", kwargs={"pk": self.application_id})
        if self.job_id:
            return reverse("jobs:detail", kwargs={"pk": self.job_id})
        if self.company_id:
            return reverse("companies:detail", kwargs={"slug": self.company.slug})
        return reverse("notifications:list")

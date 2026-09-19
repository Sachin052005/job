from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from companies.models import Company
from core.constants import JOB_STATUS_PUBLISHED
from jobs.models import Job
from saved_jobs.models import SavedJob

User = get_user_model()


class SavedJobTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.company = Company.objects.create(owner=self.employer, name="Acme")
        self.seeker = User.objects.create_user(username="seeker", password="pass12345")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="QA Engineer",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )

    def test_toggle_save_then_unsave(self):
        self.client.login(username="seeker", password="pass12345")
        url = reverse("saved_jobs:toggle", kwargs={"job_id": self.job.pk})
        self.client.post(url)
        self.assertTrue(SavedJob.objects.filter(user=self.seeker, job=self.job).exists())
        self.client.post(url)
        self.assertFalse(SavedJob.objects.filter(user=self.seeker, job=self.job).exists())

    def test_cannot_save_duplicate_via_model_constraint(self):
        SavedJob.objects.create(user=self.seeker, job=self.job)
        with self.assertRaises(Exception):
            SavedJob.objects.create(user=self.seeker, job=self.job)

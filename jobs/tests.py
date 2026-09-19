from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from companies.models import Company
from core.constants import JOB_STATUS_DRAFT, JOB_STATUS_PUBLISHED, ROLE_EMPLOYER, ROLE_JOB_SEEKER
from jobs.models import Category, Job

User = get_user_model()


class JobModelTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.company = Company.objects.create(owner=self.employer, name="Acme")

    def test_published_at_set_when_published(self):
        job = Job.objects.create(
            employer=self.employer,
            company=self.company,
            title="Django Developer",
            location="Remote",
            description="Build things",
            status=JOB_STATUS_PUBLISHED,
        )
        self.assertIsNotNone(job.published_at)

    def test_is_open_false_for_draft(self):
        job = Job.objects.create(
            employer=self.employer,
            company=self.company,
            title="Draft Job",
            location="Remote",
            description="...",
            status=JOB_STATUS_DRAFT,
        )
        self.assertFalse(job.is_open())


class JobListViewTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.company = Company.objects.create(owner=self.employer, name="Acme")
        self.category = Category.objects.create(name="Engineering")
        self.published = Job.objects.create(
            employer=self.employer, company=self.company, category=self.category,
            title="Python Developer", location="Bangalore", description="...",
            skills="Python, Django", status=JOB_STATUS_PUBLISHED,
        )
        self.draft = Job.objects.create(
            employer=self.employer, company=self.company,
            title="Hidden Draft", location="Bangalore", description="...",
            status=JOB_STATUS_DRAFT,
        )

    def test_only_published_jobs_listed(self):
        response = self.client.get(reverse("jobs:list"))
        self.assertContains(response, "Python Developer")
        self.assertNotContains(response, "Hidden Draft")

    def test_keyword_filter(self):
        response = self.client.get(reverse("jobs:list"), {"keyword": "Django"})
        self.assertContains(response, "Python Developer")

    def test_location_filter_excludes_non_matching(self):
        response = self.client.get(reverse("jobs:list"), {"location": "Mumbai"})
        self.assertNotContains(response, "Python Developer")


class JobPermissionTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme")

        self.other_employer = User.objects.create_user(username="other", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        Company.objects.create(owner=self.other_employer, name="Other Co")

        self.seeker = User.objects.create_user(username="seeker", password="pass12345")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Job A",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )

    def test_job_seeker_cannot_create_job(self):
        self.client.login(username="seeker", password="pass12345")
        response = self.client.get(reverse("jobs:create"))
        self.assertEqual(response.status_code, 403)

    def test_other_employer_cannot_edit_job(self):
        self.client.login(username="other", password="pass12345")
        response = self.client.get(reverse("jobs:edit", kwargs={"pk": self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_edit_job(self):
        self.client.login(username="employer", password="pass12345")
        response = self.client.get(reverse("jobs:edit", kwargs={"pk": self.job.pk}))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_can_view_job_detail(self):
        response = self.client.get(reverse("jobs:detail", kwargs={"pk": self.job.pk}))
        self.assertEqual(response.status_code, 200)

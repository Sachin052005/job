from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from companies.models import Company
from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER

User = get_user_model()


class CompanyModelTests(TestCase):
    def test_slug_auto_generated_and_unique(self):
        owner1 = User.objects.create_user(username="emp1", password="pass12345")
        owner2 = User.objects.create_user(username="emp2", password="pass12345")
        c1 = Company.objects.create(owner=owner1, name="Acme Corp")
        c2 = Company.objects.create(owner=owner2, name="Acme Corp".upper() + " ")
        self.assertEqual(c1.slug, "acme-corp")
        self.assertNotEqual(c1.slug, c2.slug)


class CompanyOwnershipTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()

        self.other_employer = User.objects.create_user(username="other", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()

        self.seeker = User.objects.create_user(username="seeker", password="pass12345")

        self.company = Company.objects.create(owner=self.employer, name="Initech")

    def test_job_seeker_cannot_create_company(self):
        self.client.login(username="seeker", password="pass12345")
        response = self.client.get(reverse("companies:create"))
        self.assertEqual(response.status_code, 403)

    def test_other_employer_cannot_edit_company(self):
        self.client.login(username="other", password="pass12345")
        response = self.client.get(reverse("companies:edit", kwargs={"slug": self.company.slug}))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_edit_company(self):
        self.client.login(username="employer", password="pass12345")
        response = self.client.get(reverse("companies:edit", kwargs={"slug": self.company.slug}))
        self.assertEqual(response.status_code, 200)

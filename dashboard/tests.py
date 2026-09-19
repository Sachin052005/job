from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from companies.models import Company
from core.constants import ROLE_EMPLOYER

User = get_user_model()


class DashboardViewTests(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)

    def test_seeker_gets_seeker_dashboard(self):
        User.objects.create_user(username="seeker", password="pass12345")
        self.client.login(username="seeker", password="pass12345")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/seeker_dashboard.html")

    def test_employer_gets_employer_dashboard(self):
        employer = User.objects.create_user(username="employer", password="pass12345")
        employer.profile.role = ROLE_EMPLOYER
        employer.profile.save()
        Company.objects.create(owner=employer, name="Acme")
        self.client.login(username="employer", password="pass12345")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/employer_dashboard.html")

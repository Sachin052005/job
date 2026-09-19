from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER
from core.validators import validate_profile_url

User = get_user_model()


class ProfileSignalTests(TestCase):
    def test_profile_created_on_user_creation(self):
        user = User.objects.create_user(username="alice", password="pass12345")
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.role, ROLE_JOB_SEEKER)


class RegistrationTests(TestCase):
    def test_register_creates_user_and_profile_with_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "bob",
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob@example.com",
                "role": ROLE_EMPLOYER,
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="bob")
        self.assertEqual(user.profile.role, ROLE_EMPLOYER)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="existing", email="dup@example.com", password="pass12345")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newuser",
                "first_name": "New",
                "email": "dup@example.com",
                "role": ROLE_JOB_SEEKER,
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="pass12345")

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)

    def test_profile_view_when_logged_in(self):
        self.client.login(username="carol", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)


class ProfileLinkValidatorTests(TestCase):
    def test_valid_linkedin_url_accepted(self):
        validate_profile_url("https://www.linkedin.com/in/example", kind="linkedin")

    def test_non_linkedin_host_rejected_for_linkedin_kind(self):
        with self.assertRaises(ValidationError):
            validate_profile_url("https://example.com/in/someone", kind="linkedin")

    def test_valid_github_url_accepted(self):
        validate_profile_url("https://github.com/example", kind="github")

    def test_javascript_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            validate_profile_url("javascript:alert(1)", kind="github")

    def test_blank_url_is_allowed(self):
        validate_profile_url("", kind="linkedin")


class ProfileCompletenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="pass12345")
        self.profile = self.user.profile

    def test_empty_profile_has_low_completion_and_missing_sections(self):
        self.assertLess(self.profile.completion_percent(), 50)
        self.assertIn("Resume", self.profile.missing_sections())
        self.assertIn("Skills", self.profile.missing_sections())

    def test_easy_apply_requires_resume_and_skills(self):
        self.assertFalse(self.profile.is_easy_apply_ready())
        self.assertIn("Resume", self.profile.missing_easy_apply_fields())
        self.assertIn("Skills", self.profile.missing_easy_apply_fields())

    def test_easy_apply_ready_once_resume_and_skills_present(self):
        self.profile.skills = "Python, Django"
        self.profile.resume.name = "resumes/fake.pdf"
        self.profile.save()
        self.assertTrue(self.profile.is_easy_apply_ready())
        self.assertEqual(self.profile.missing_easy_apply_fields(), [])

    def test_completion_increases_with_filled_sections(self):
        before = self.profile.completion_percent()
        self.profile.headline = "Aspiring Developer"
        self.profile.location = "Bengaluru"
        self.profile.linkedin_url = "https://www.linkedin.com/in/dave"
        self.profile.save()
        self.assertGreater(self.profile.completion_percent(), before)

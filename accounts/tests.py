import re
from datetime import date
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ProfileForm
from accounts.models import (
    Accomplishment,
    CandidateSkill,
    CareerPreference,
    Education,
    Internship,
    JobAlert,
    Language,
    Profile,
    Project,
    SocialAccount,
    WorkExperience,
)
from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER
from core.validators import validate_profile_url

User = get_user_model()


def make_certificate():
    return SimpleUploadedFile("cert.pdf", b"%PDF-1.4 fake certificate", content_type="application/pdf")


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

    def test_easy_apply_requires_full_profile(self):
        self.assertFalse(self.profile.is_easy_apply_ready())
        missing = self.profile.missing_easy_apply_fields()
        for label in ("Full name", "Email", "Resume", "Skills", "Phone number", "Location", "LinkedIn profile", "GitHub profile"):
            self.assertIn(label, missing)

    def test_easy_apply_ready_once_all_required_fields_present(self):
        self.user.first_name = "Dave"
        self.user.email = "dave@example.com"
        self.user.save()
        self.profile.skills = "Python, Django"
        self.profile.resume.name = "resumes/fake.pdf"
        self.profile.phone = "9876543210"
        self.profile.location = "Salem, Tamil Nadu"
        self.profile.linkedin_url = "https://www.linkedin.com/in/dave"
        self.profile.github_url = "https://github.com/dave"
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


class WebsiteFieldHiddenTests(TestCase):
    def test_website_url_not_in_candidate_profile_form(self):
        self.assertNotIn("website_url", ProfileForm.base_fields)


class CareerPreferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="erin", password="pass12345")
        self.client.login(username="erin", password="pass12345")

    def test_edit_page_does_not_create_row_on_get(self):
        self.client.get(reverse("accounts:profile_career_preferences_edit"))
        self.assertFalse(CareerPreference.objects.filter(profile=self.user.profile).exists())

    def test_saving_creates_career_preference(self):
        response = self.client.post(
            reverse("accounts:profile_career_preferences_edit"),
            {"job_search_status": "actively_looking"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CareerPreference.objects.filter(profile=self.user.profile).exists())


class EducationCRUDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="frank", password="pass12345")
        self.other = User.objects.create_user(username="gina", password="pass12345")
        self.client.login(username="frank", password="pass12345")

    def test_create_education(self):
        response = self.client.post(
            reverse("accounts:profile_education_add"),
            {
                "level": "undergraduate",
                "degree": "B.Tech",
                "specialization": "Computer Science",
                "institution": "ABC Engineering College",
                "university": "XYZ University",
                "start_year": 2020,
                "end_year": 2024,
                "grade": "8.5 CGPA",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.education_records.count(), 1)

    def test_cannot_edit_other_users_education(self):
        edu = Education.objects.create(
            profile=self.other.profile, degree="B.Sc", institution="Other College", start_year=2019, end_year=2022
        )
        response = self.client.get(reverse("accounts:profile_education_edit", args=[edu.pk]))
        self.assertEqual(response.status_code, 404)

    def test_delete_education(self):
        edu = Education.objects.create(
            profile=self.user.profile, degree="B.Sc", institution="College", start_year=2019, end_year=2022
        )
        response = self.client.post(reverse("accounts:profile_education_delete", args=[edu.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Education.objects.filter(pk=edu.pk).exists())


class WorkExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="harry", password="pass12345")
        self.client.login(username="harry", password="pass12345")

    def test_requires_end_date_unless_current(self):
        response = self.client.post(
            reverse("accounts:profile_experience_add"),
            {"company": "Acme", "designation": "Developer", "start_date": "2022-01-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End date is required")
        self.assertEqual(self.user.profile.experience_records.count(), 0)

    def test_current_job_clears_end_date(self):
        response = self.client.post(
            reverse("accounts:profile_experience_add"),
            {
                "company": "Acme",
                "designation": "Developer",
                "start_date": "2022-01-01",
                "is_current": "on",
                "end_date": "2023-01-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        exp = self.user.profile.experience_records.get()
        self.assertIsNone(exp.end_date)
        self.assertTrue(exp.is_current)

    def test_cannot_delete_other_users_experience(self):
        other = User.objects.create_user(username="iris", password="pass12345")
        exp = WorkExperience.objects.create(
            profile=other.profile,
            company="Acme",
            designation="Dev",
            start_date=date(2022, 1, 1),
            is_current=True,
        )
        response = self.client.post(reverse("accounts:profile_experience_delete", args=[exp.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WorkExperience.objects.filter(pk=exp.pk).exists())


class ProjectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jack", password="pass12345")
        self.client.login(username="jack", password="pass12345")

    def test_create_project(self):
        response = self.client.post(
            reverse("accounts:profile_projects_add"),
            {"title": "Portfolio Site", "technologies": "Django, HTMX"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.projects.count(), 1)

    def test_delete_project(self):
        project = Project.objects.create(profile=self.user.profile, title="Old Project")
        response = self.client.post(reverse("accounts:profile_projects_delete", args=[project.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())


class InternshipTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jane", password="pass12345")
        self.client.login(username="jane", password="pass12345")

    def test_create_internship_with_certificate(self):
        response = self.client.post(
            reverse("accounts:profile_internships_add"),
            {
                "company": "Acme",
                "role": "Intern",
                "start_date": "2023-05-01",
                "end_date": "2023-07-01",
                "certificate": make_certificate(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.internships.count(), 1)

    def test_cannot_edit_other_users_internship(self):
        other = User.objects.create_user(username="kyle", password="pass12345")
        internship = Internship.objects.create(
            profile=other.profile, company="Acme", role="Intern", start_date=date(2022, 1, 1)
        )
        response = self.client.get(reverse("accounts:profile_internships_edit", args=[internship.pk]))
        self.assertEqual(response.status_code, 404)


class AccomplishmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="karen", password="pass12345")
        self.client.login(username="karen", password="pass12345")

    def test_create_accomplishment(self):
        response = self.client.post(
            reverse("accounts:profile_accomplishments_add"),
            {"category": "certification", "title": "AWS Certified"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.accomplishments.count(), 1)

    def test_delete_accomplishment(self):
        accomplishment = Accomplishment.objects.create(profile=self.user.profile, title="Old Award")
        response = self.client.post(reverse("accounts:profile_accomplishments_delete", args=[accomplishment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Accomplishment.objects.filter(pk=accomplishment.pk).exists())


class LanguageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="leo", password="pass12345")
        self.client.login(username="leo", password="pass12345")

    def test_create_language(self):
        response = self.client.post(
            reverse("accounts:profile_languages_add"), {"name": "English", "proficiency": "fluent"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.profile.languages.count(), 1)

    def test_duplicate_language_rejected(self):
        Language.objects.create(profile=self.user.profile, name="English", proficiency="fluent")
        response = self.client.post(
            reverse("accounts:profile_languages_add"), {"name": "English", "proficiency": "native"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.profile.languages.count(), 1)


class CandidateSkillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mike", password="pass12345")
        self.client.login(username="mike", password="pass12345")

    def test_skill_name_normalized_on_save(self):
        response = self.client.post(
            reverse("accounts:profile_skills_add"), {"name": "ReactJS", "proficiency": "advanced"}
        )
        self.assertEqual(response.status_code, 302)
        skill = self.user.profile.structured_skills.get()
        self.assertEqual(skill.name, "React")

    def test_duplicate_skill_rejected(self):
        CandidateSkill.objects.create(profile=self.user.profile, name="Python")
        response = self.client.post(reverse("accounts:profile_skills_add"), {"name": "Python"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.profile.structured_skills.count(), 1)

    def test_cannot_delete_other_users_skill(self):
        other = User.objects.create_user(username="nancy", password="pass12345")
        skill = CandidateSkill.objects.create(profile=other.profile, name="Java")
        response = self.client.post(reverse("accounts:profile_skills_delete", args=[skill.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CandidateSkill.objects.filter(pk=skill.pk).exists())


class ProfileCompletionBucketsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="olivia", password="pass12345")
        self.profile = self.user.profile

    def test_career_preference_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        CareerPreference.objects.create(profile=self.profile)
        self.assertGreater(self.profile.completion_percent(), before)

    def test_education_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        Education.objects.create(profile=self.profile, degree="B.Tech", institution="X", start_year=2020)
        self.assertGreater(self.profile.completion_percent(), before)

    def test_structured_skill_increases_completion_without_csv_skills(self):
        before = self.profile.completion_percent()
        CandidateSkill.objects.create(profile=self.profile, name="Python")
        self.assertGreater(self.profile.completion_percent(), before)

    def test_experience_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        WorkExperience.objects.create(
            profile=self.profile, company="Acme", designation="Dev", start_date=date(2022, 1, 1), is_current=True
        )
        self.assertGreater(self.profile.completion_percent(), before)

    def test_projects_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        Project.objects.create(profile=self.profile, title="Portfolio")
        self.assertGreater(self.profile.completion_percent(), before)

    def test_internships_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        Internship.objects.create(profile=self.profile, company="Acme", role="Intern", start_date=date(2022, 1, 1))
        self.assertGreater(self.profile.completion_percent(), before)

    def test_languages_bucket_increases_completion(self):
        before = self.profile.completion_percent()
        Language.objects.create(profile=self.profile, name="English")
        self.assertGreater(self.profile.completion_percent(), before)

    def test_fully_completed_profile_reaches_100_percent(self):
        self.profile.headline = "Developer"
        self.profile.location = "Bengaluru"
        self.profile.phone = "9999999999"
        self.profile.summary = "Experienced developer."
        self.profile.skills = "Python"
        self.profile.linkedin_url = "https://www.linkedin.com/in/olivia"
        self.profile.github_url = "https://github.com/olivia"
        self.profile.resume.name = "resumes/fake.pdf"
        self.profile.save()
        CareerPreference.objects.create(profile=self.profile)
        Education.objects.create(profile=self.profile, degree="B.Tech", institution="X", start_year=2020)
        WorkExperience.objects.create(
            profile=self.profile, company="Acme", designation="Dev", start_date=date(2022, 1, 1), is_current=True
        )
        Project.objects.create(profile=self.profile, title="Portfolio")
        Internship.objects.create(profile=self.profile, company="Acme", role="Intern", start_date=date(2022, 1, 1))
        Language.objects.create(profile=self.profile, name="English")
        self.assertEqual(self.profile.completion_percent(), 100)

    def test_missing_sections_lists_new_buckets(self):
        missing = self.profile.missing_sections()
        for label in ["Career preferences", "Education", "Languages", "Internships", "Projects", "Experience"]:
            self.assertIn(label, missing)


class ActivityStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="peter", password="pass12345")
        self.profile = self.user.profile

    def test_not_available_when_never_active(self):
        self.assertEqual(self.profile.activity_status(), "Not available")

    def test_active_within_a_day(self):
        self.profile.last_activity_at = timezone.now()
        self.assertEqual(self.profile.activity_status(), "Active")

    def test_recently_active_within_a_week(self):
        self.profile.last_activity_at = timezone.now() - timezone.timedelta(days=3)
        self.assertEqual(self.profile.activity_status(), "Recently active")

    def test_away_within_a_month(self):
        self.profile.last_activity_at = timezone.now() - timezone.timedelta(days=20)
        self.assertEqual(self.profile.activity_status(), "Away")

    def test_not_available_after_a_month(self):
        self.profile.last_activity_at = timezone.now() - timezone.timedelta(days=45)
        self.assertEqual(self.profile.activity_status(), "Not available")

    def test_touch_last_updated_sets_both_fields(self):
        self.assertIsNone(self.profile.profile_last_updated)
        self.profile.touch_last_updated()
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.profile_last_updated)
        self.assertIsNotNone(self.profile.last_activity_at)

    def test_login_records_activity(self):
        self.assertIsNone(self.profile.last_activity_at)
        self.client.login(username="peter", password="pass12345")
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.last_activity_at)


class ProfileEditTouchesLastUpdatedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="quinn", password="pass12345")
        self.client.login(username="quinn", password="pass12345")

    def test_adding_education_touches_profile_last_updated(self):
        self.assertIsNone(self.user.profile.profile_last_updated)
        self.client.post(
            reverse("accounts:profile_education_add"),
            {"degree": "B.Tech", "institution": "College", "start_year": 2020},
        )
        self.user.profile.refresh_from_db()
        self.assertIsNotNone(self.user.profile.profile_last_updated)


class GoogleOAuthTests(TestCase):
    def setUp(self):
        self.session_state = None

    def _prime_session_state(self):
        session = self.client.session
        session["google_oauth_state"] = "teststate123"
        session.save()
        return "teststate123"

    def test_callback_rejects_mismatched_state(self):
        self._prime_session_state()
        response = self.client.get(reverse("accounts:google_callback"), {"state": "wrong", "code": "abc"})
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.count(), 0)

    @patch("accounts.views.exchange_code_for_userinfo")
    def test_new_user_created_and_sent_to_welcome(self, mock_exchange):
        state = self._prime_session_state()
        mock_exchange.return_value = {
            "sub": "google-sub-1", "email": "newgoogleuser@example.com",
            "given_name": "New", "family_name": "User",
        }
        response = self.client.get(reverse("accounts:google_callback"), {"state": state, "code": "abc"})
        self.assertRedirects(response, reverse("accounts:google_welcome"))
        user = User.objects.get(email="newgoogleuser@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(user=user, provider_user_id="google-sub-1").exists())

    @patch("accounts.views.exchange_code_for_userinfo")
    def test_existing_social_account_logs_in(self, mock_exchange):
        user = User.objects.create_user(username="googler", email="googler@example.com", password="unused12345")
        SocialAccount.objects.create(user=user, provider="google", provider_user_id="sub-existing")
        state = self._prime_session_state()
        mock_exchange.return_value = {"sub": "sub-existing", "email": "googler@example.com"}
        response = self.client.get(reverse("accounts:google_callback"), {"state": state, "code": "abc"})
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @patch("accounts.views.exchange_code_for_userinfo")
    def test_existing_email_without_social_account_is_not_auto_linked(self, mock_exchange):
        User.objects.create_user(username="pwuser", email="pwuser@example.com", password="pass12345")
        state = self._prime_session_state()
        mock_exchange.return_value = {"sub": "sub-new", "email": "pwuser@example.com"}
        response = self.client.get(reverse("accounts:google_callback"), {"state": state, "code": "abc"})
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(SocialAccount.objects.filter(provider_user_id="sub-new").exists())

    def test_welcome_sets_role_and_redirects(self):
        user = User.objects.create_user(username="welcomeuser", password="pass12345")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:google_welcome"), {"choice": "employer"})
        self.assertRedirects(response, reverse("companies:create"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.role, ROLE_EMPLOYER)

    @patch("accounts.views.exchange_code_for_userinfo")
    def test_link_requires_matching_authenticated_user(self, mock_exchange):
        user = User.objects.create_user(username="linkuser", password="pass12345")
        self.client.force_login(user)
        session = self.client.session
        session["google_oauth_state"] = "linkstate"
        session["google_oauth_link_user_id"] = 99999  # deliberately not this user's id
        session.save()
        mock_exchange.return_value = {"sub": "sub-link", "email": "link@example.com"}
        response = self.client.get(reverse("accounts:google_callback"), {"state": "linkstate", "code": "abc"})
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(SocialAccount.objects.filter(provider_user_id="sub-link").exists())


class JobAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alertuser", password="pass12345")
        self.client.login(username="alertuser", password="pass12345")

    def test_create_job_alert(self):
        response = self.client.post(
            reverse("job_alerts:create"),
            {"name": "Python roles", "keywords": "python, django", "frequency": "daily", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.job_alerts.count(), 1)

    def test_empty_state(self):
        response = self.client.get(reverse("job_alerts:list"))
        self.assertContains(response, "No job alerts created yet.")

    def test_toggle_alert(self):
        alert = JobAlert.objects.create(user=self.user, name="Test", is_active=True)
        self.client.post(reverse("job_alerts:toggle", kwargs={"pk": alert.pk}))
        alert.refresh_from_db()
        self.assertFalse(alert.is_active)

    def test_delete_alert(self):
        alert = JobAlert.objects.create(user=self.user, name="Test")
        self.client.post(reverse("job_alerts:delete", kwargs={"pk": alert.pk}))
        self.assertFalse(JobAlert.objects.filter(pk=alert.pk).exists())

    def test_matches_keyword_and_location(self):
        from companies.models import Company
        from core.constants import JOB_STATUS_PUBLISHED
        from jobs.models import Job

        employer = User.objects.create_user(username="alertemployer", password="pass12345")
        employer.profile.role = ROLE_EMPLOYER
        employer.profile.save()
        company = Company.objects.create(owner=employer, name="AlertCo")
        job = Job.objects.create(
            employer=employer, company=company, title="Python Developer", location="Bengaluru",
            description="...", status=JOB_STATUS_PUBLISHED,
        )
        alert = JobAlert.objects.create(user=self.user, name="Python", keywords="python", location="Bengaluru")
        self.assertTrue(alert.matches(job))
        alert.location = "Chennai"
        self.assertFalse(alert.matches(job))


class SettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="settingsuser", password="pass12345")
        self.client.login(username="settingsuser", password="pass12345")

    def test_account_update(self):
        response = self.client.post(
            reverse("settings:account"),
            {"first_name": "New", "last_name": "Name", "email": "new@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")

    def test_appearance_theme_persists(self):
        response = self.client.post(reverse("settings:appearance"), {"theme": "dark"})
        self.assertEqual(response.status_code, 302)
        self.user.settings.refresh_from_db()
        self.assertEqual(self.user.settings.theme, "dark")

        # Simulate refresh: theme should still be "dark" on the next request.
        response = self.client.get(reverse("settings:appearance"))
        self.assertContains(response, 'data-theme="dark"')

    def test_notifications_toggle_persists(self):
        response = self.client.post(
            reverse("settings:notifications"),
            {
                "notify_job_alerts": "on",
                "notify_application_updates": "",
                "notify_recruiter_updates": "on",
                "notify_company_updates": "on",
                "notify_interview_reminders": "on",
                "notify_system": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.settings.refresh_from_db()
        self.assertFalse(self.user.settings.notify_application_updates)

    def test_privacy_update(self):
        response = self.client.post(
            reverse("settings:privacy"),
            {
                "profile_visibility": "private",
                "recruiters_can_view_profile": "",
                "recruiters_can_download_resume": "",
                "recruiters_can_contact": "",
                "show_in_recruiter_search": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.settings.refresh_from_db()
        self.assertEqual(self.user.settings.profile_visibility, "private")
        self.assertFalse(self.user.settings.show_in_recruiter_search)

    def test_password_change_success_message(self):
        response = self.client.post(
            reverse("settings:security_password"),
            {"old_password": "pass12345", "new_password1": "NewPass98765", "new_password2": "NewPass98765"},
            follow=True,
        )
        self.assertContains(response, "Password changed successfully.")

    def test_settings_pages_work_for_user_missing_usersettings_row(self):
        """Regression test: accounts created before UserSettings existed (or
        via any path that bypasses the post_save signal) must not 500 on
        Appearance/Notifications/Privacy - this is exactly what was broken.
        """
        from accounts.models import UserSettings

        UserSettings.objects.filter(user=self.user).delete()
        self.assertFalse(UserSettings.objects.filter(user=self.user).exists())

        for name in ("settings:appearance", "settings:notifications", "settings:privacy"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"{name} should not 500 for a user with no UserSettings row")

        self.assertTrue(UserSettings.objects.filter(user=self.user).exists())

    def test_application_preferences_save_and_reload_with_only_visible_fields(self):
        """Regression test: CareerPreference.willing_to_relocate/job_search_status
        must not be silently-required, since the settings template never
        renders them - previously every save here failed validation with no
        visible error and nothing was ever persisted.
        """
        self.user.profile.role = ROLE_JOB_SEEKER
        self.user.profile.save()
        response = self.client.post(
            reverse("settings:application_preferences"),
            {
                "preferred_industry": "Fintech",
                "preferred_location": "Chennai",
                "employment_type": "full_time",
                "work_mode": "remote",
                "expected_salary": 900000,
                "notice_period": "30_days",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        preference = self.user.profile.career_preference
        self.assertEqual(preference.preferred_location, "Chennai")

        response = self.client.get(reverse("settings:application_preferences"))
        self.assertContains(response, "Chennai")
        self.assertContains(response, "Fintech")


class SettingsAccessControlTests(TestCase):
    def test_unauthenticated_settings_access_redirects_with_safe_next(self):
        # Application Preferences is gated by JobSeekerRequiredMixin (role +
        # login), not plain LoginRequiredMixin like the other three - its
        # handle_no_permission() used to drop `next` entirely (redirect to
        # bare /accounts/login/), unlike Appearance/Notifications/Privacy.
        for name, path in [
            ("settings:appearance", "/settings/appearance/"),
            ("settings:notifications", "/settings/notifications/"),
            ("settings:privacy", "/settings/privacy/"),
            ("settings:application_preferences", "/settings/application-preferences/"),
        ]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, f"/accounts/login/?next={path}")


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="daveuser",
            email="dave@example.com",
            password="OldPass123",
        )

    def _extract_confirm_url(self, email_body):
        match = re.search(r"(/accounts/password/reset/confirm/\S+/\S+/)", email_body)
        self.assertIsNotNone(match, "Reset link not found in email body")
        return match.group(1)

    def test_forgot_password_page_loads(self):
        response = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send Reset Link")

    def test_login_page_has_forgot_password_link(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:password_reset"))

    def test_valid_email_sends_reset_email_to_registered_address(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "dave@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["dave@example.com"])
        self.assertEqual(sent.from_email, "idpsachin@gmail.com")
        self.assertEqual(sent.subject, "Reset your TalentPanda password")

    def test_unknown_email_returns_same_generic_response_and_sends_nothing(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "nobody@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow_changes_password(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "dave@example.com"})
        confirm_url = self._extract_confirm_url(mail.outbox[0].body)

        # First GET redirects to the session-backed "set-password" URL.
        response = self.client.get(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)
        set_password_url = response.request["PATH_INFO"]

        response = self.client.post(
            set_password_url,
            {"new_password1": "BrandNewPass456", "new_password2": "BrandNewPass456"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        self.assertFalse(self.client.login(username="daveuser", password="OldPass123"))
        self.assertTrue(self.client.login(username="daveuser", password="BrandNewPass456"))

    def test_invalid_token_is_rejected(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "dave@example.com"})
        confirm_url = self._extract_confirm_url(mail.outbox[0].body)
        uidb64 = confirm_url.strip("/").split("/")[-2]
        bad_url = f"/accounts/password/reset/confirm/{uidb64}/not-a-valid-token/"

        response = self.client.get(bad_url, follow=True)
        self.assertContains(response, "This password reset link is invalid or has expired.")

    def test_password_reset_requires_csrf(self):
        strict_client = Client(enforce_csrf_checks=True)
        response = strict_client.post(
            reverse("accounts:password_reset"),
            {"email": "dave@example.com"},
        )
        self.assertEqual(response.status_code, 403)

    def test_smtp_failure_still_shows_generic_success_page(self):
        with patch(
            "django.contrib.auth.forms.PasswordResetForm.save",
            side_effect=SMTPException("connection refused"),
        ):
            response = self.client.post(
                reverse("accounts:password_reset"),
                {"email": "dave@example.com"},
            )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))


class StudentPerformanceRangeFilterTests(TestCase):
    """The Profile Performance chart and the activity details list below it
    must always share the exact same timezone-aware date range - selecting
    a range narrows both together, never just the chart (spec sections
    23-26)."""

    def setUp(self):
        from datetime import timedelta

        from activity.models import StudentActivity

        self.student = User.objects.create_user(username="perf_student", password="pass12345")
        self.student.profile.role = ROLE_JOB_SEEKER
        self.student.profile.save()
        self.client.login(username="perf_student", password="pass12345")

        now = timezone.now()
        self.today_activity = StudentActivity.objects.create(
            student=self.student, event_type="profile_view",
        )
        self.today_activity.created_at = now
        self.today_activity.save(update_fields=["created_at"])

        self.old_activity = StudentActivity.objects.create(student=self.student, event_type="profile_view")
        self.old_activity.created_at = now - timedelta(days=45)
        self.old_activity.save(update_fields=["created_at"])

    def test_default_range_is_last_30_days(self):
        response = self.client.get(reverse("accounts:performance"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["range_key"], "30d")

    @staticmethod
    def _total_chart_activity(response):
        return sum(sum(series["data"]) for series in response.context["chart_series"])

    def test_today_range_excludes_older_activity_from_chart_and_details(self):
        response = self.client.get(reverse("accounts:performance"), {"range": "today"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._total_chart_activity(response), 1)
        self.assertTrue(response.context["chart_has_data"])
        timeline_items = [item for group in response.context["timeline"] for item in group["items"]]
        self.assertEqual(len(timeline_items), 1)

    def test_90_day_range_includes_both_activities(self):
        response = self.client.get(reverse("accounts:performance"), {"range": "90d"})
        self.assertEqual(self._total_chart_activity(response), 2)
        timeline_items = [item for group in response.context["timeline"] for item in group["items"]]
        self.assertEqual(len(timeline_items), 2)

    def test_custom_range_uses_given_start_and_end(self):
        from datetime import timedelta

        start = (timezone.localdate() - timedelta(days=50)).isoformat()
        end = (timezone.localdate() - timedelta(days=40)).isoformat()
        response = self.client.get(
            reverse("accounts:performance"), {"range": "custom", "start": start, "end": end}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._total_chart_activity(response), 1)  # only the 45-day-old activity falls in this window

    def test_invalid_range_falls_back_to_default(self):
        response = self.client.get(reverse("accounts:performance"), {"range": "not-a-real-range"})
        self.assertEqual(response.context["range_key"], "30d")
        self.assertEqual(len(mail.outbox), 0)

    def test_chart_series_are_never_fabricated(self):
        response = self.client.get(reverse("accounts:performance"), {"range": "90d"})
        series_by_key = {s["key"]: s for s in response.context["chart_series"]}
        self.assertEqual(set(series_by_key), {"profile_views", "search_appearances", "recruiter_actions"})
        # Both seeded activities are profile_view events - they must land on
        # the Profile Views line only, never fabricated onto the others.
        self.assertEqual(sum(series_by_key["profile_views"]["data"]), 2)
        self.assertEqual(sum(series_by_key["search_appearances"]["data"]), 0)
        self.assertEqual(sum(series_by_key["recruiter_actions"]["data"]), 0)


class StudentPerformanceEmptyStateTests(TestCase):
    def test_no_activity_reports_no_chart_data(self):
        student = User.objects.create_user(username="empty_perf_student", password="pass12345")
        student.profile.role = ROLE_JOB_SEEKER
        student.profile.save()
        self.client.login(username="empty_perf_student", password="pass12345")

        response = self.client.get(reverse("accounts:performance"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["chart_has_data"])
        for series in response.context["chart_series"]:
            self.assertEqual(sum(series["data"]), 0)

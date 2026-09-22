from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from applications.models import Application
from companies.models import Company, CompanyReview
from core.constants import APPLICATION_STATUS_SHORTLISTED, JOB_STATUS_DRAFT, JOB_STATUS_PUBLISHED, ROLE_EMPLOYER
from helpcenter.models import Feedback
from jobs.models import Job
from notifications.models import Notification

User = get_user_model()


def _resume():
    return SimpleUploadedFile("resume.pdf", b"dummy resume bytes", content_type="application/pdf")


class LoginRedirectTests(TestCase):
    """There is exactly one login page (/accounts/login/) for everyone - a
    staff or superuser account is redirected to /admin-panel/ after
    authenticating there; every other user keeps the existing dashboard
    redirect. No separate /admin-login/ page exists."""

    def setUp(self):
        self.student = User.objects.create_user("student1", "student1@example.com", "pass12345")
        self.hr = User.objects.create_user("hr1", "hr1@example.com", "pass12345")
        self.hr.profile.role = ROLE_EMPLOYER
        self.hr.profile.save()
        self.staff = User.objects.create_user("staffuser", "staff@example.com", "pass12345", is_staff=True)
        self.superuser = User.objects.create_user(
            "superuser1", "superuser1@example.com", "pass12345", is_staff=False, is_superuser=True
        )
        self.regular = User.objects.create_user("regularuser", "regular@example.com", "pass12345")

    def _login(self, username, **extra):
        payload = {"username": username, "password": "pass12345"}
        payload.update(extra)
        return self.client.post(reverse("accounts:login"), payload)

    def test_student_login_goes_to_normal_destination(self):
        response = self._login("student1")
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_hr_login_goes_to_normal_destination(self):
        response = self._login("hr1")
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_superuser_login_redirects_to_admin_panel(self):
        response = self._login("superuser1")
        self.assertRedirects(response, reverse("adminpanel:dashboard"))

    def test_staff_login_redirects_to_admin_panel(self):
        response = self._login("staffuser")
        self.assertRedirects(response, reverse("adminpanel:dashboard"))

    def test_anonymous_admin_panel_redirects_to_accounts_login(self):
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('adminpanel:dashboard')}"
        )

    def test_non_admin_cannot_access_admin_panel(self):
        self.client.login(username="regularuser", password="pass12345")
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_admin_panel(self):
        self.client.login(username="staffuser", password="pass12345")
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_separate_admin_login_route_no_longer_exists(self):
        response = self.client.get("/admin-login/")
        self.assertEqual(response.status_code, 404)

    def test_non_admin_next_param_cannot_reach_admin_panel_via_login(self):
        admin_panel_url = reverse("adminpanel:dashboard")
        response = self._login("regularuser", next=admin_panel_url)
        self.assertNotEqual(response.url, admin_panel_url)
        self.assertFalse(response.url.startswith(admin_panel_url))

    def test_admin_logout_redirects_to_accounts_login(self):
        self.client.login(username="staffuser", password="pass12345")
        response = self.client.post(reverse("accounts:logout"), {"next": reverse("accounts:login")})
        self.assertRedirects(response, reverse("accounts:login"))

    def test_django_admin_still_available(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_public_home_still_available(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_admin_logo_uses_existing_hero_image(self):
        image_path = Path(settings.BASE_DIR) / "static" / "images" / "job-hero.png"
        self.assertTrue(image_path.exists())
        self.client.login(username="staffuser", password="pass12345")
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertContains(response, "images/job-hero.png")


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staffuser2", "staff2@example.com", "pass12345", is_staff=True)
        self.client.login(username="staffuser2", password="pass12345")
        self.owner = User.objects.create_user("owner1", "owner1@example.com", "pass12345")
        self.company = Company.objects.create(owner=self.owner, name="Acme Corp")
        self.employer = User.objects.create_user("employer1", "employer1@example.com", "pass12345")
        Job.objects.create(
            employer=self.employer, company=self.company, title="Backend Dev",
            location="Chennai", description="Build things.", status=JOB_STATUS_PUBLISHED,
        )

    def test_dashboard_counts_come_from_database(self):
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(response.context["total_jobs"], 1)
        self.assertEqual(response.context["published_jobs"], 1)
        self.assertEqual(response.context["company_count"], 1)


class UserCrudTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin1", "admin1@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin1", password="pass12345")
        self.target = User.objects.create_user("target1", "target1@example.com", "pass12345")

    def test_user_list_search(self):
        response = self.client.get(reverse("adminpanel:user_list"), {"q": "target1"})
        self.assertContains(response, "target1")

    def test_user_list_pagination_context(self):
        response = self.client.get(reverse("adminpanel:user_list"))
        self.assertIn("page_obj", response.context)

    def test_user_edit_updates_database(self):
        url = reverse("adminpanel:user_edit", args=[self.target.pk])
        self.client.post(
            url,
            {
                "username": "target1", "email": "changed@example.com", "first_name": "T", "last_name": "One",
                "is_active": "on", "is_staff": "", "is_superuser": "",
            },
        )
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, "changed@example.com")

    def test_user_delete_requires_post_and_confirms_first(self):
        url = reverse("adminpanel:user_delete", args=[self.target.pk])
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())
        self.client.post(url)
        self.assertFalse(User.objects.filter(pk=self.target.pk).exists())

    def test_cannot_delete_own_account(self):
        url = reverse("adminpanel:user_delete", args=[self.staff.pk])
        self.client.post(url)
        self.assertTrue(User.objects.filter(pk=self.staff.pk).exists())

    def test_bulk_deactivate(self):
        url = reverse("adminpanel:user_list")
        self.client.post(url, {"bulk_action": "deactivate", "selected": [self.target.pk]})
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)


class JobCrudTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin2", "admin2@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin2", password="pass12345")
        self.owner = User.objects.create_user("owner2", "owner2@example.com", "pass12345")
        self.company = Company.objects.create(owner=self.owner, name="Beta Corp")
        self.employer = User.objects.create_user("employer2", "employer2@example.com", "pass12345")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="QA Engineer",
            location="Pune", description="Test things.", status=JOB_STATUS_DRAFT,
        )

    def test_bulk_publish(self):
        url = reverse("adminpanel:job_list")
        self.client.post(url, {"bulk_action": "publish", "selected": [self.job.pk]})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JOB_STATUS_PUBLISHED)

    def test_job_detail_view(self):
        response = self.client.get(reverse("adminpanel:job_detail", args=[self.job.pk]))
        self.assertContains(response, "QA Engineer")

    def test_job_delete_removes_record(self):
        url = reverse("adminpanel:job_delete", args=[self.job.pk])
        self.client.post(url)
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())


class ApplicationStatusTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin3", "admin3@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin3", password="pass12345")
        self.owner = User.objects.create_user("owner3", "owner3@example.com", "pass12345")
        self.company = Company.objects.create(owner=self.owner, name="Gamma Corp")
        self.employer = User.objects.create_user("employer3", "employer3@example.com", "pass12345")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Data Analyst",
            location="Remote", description="Analyze data.", status=JOB_STATUS_PUBLISHED,
        )
        self.applicant = User.objects.create_user("applicant1", "applicant1@example.com", "pass12345")
        self.application = Application.objects.create(
            job=self.job, applicant=self.applicant, first_name="App", last_name="Licant",
            email="applicant1@example.com", resume=_resume(),
        )

    def test_status_update_records_history_via_model_method(self):
        url = reverse("adminpanel:application_status", args=[self.application.pk])
        self.client.post(url, {"status": APPLICATION_STATUS_SHORTLISTED})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, APPLICATION_STATUS_SHORTLISTED)
        self.assertEqual(self.application.status_history.count(), 1)
        self.assertEqual(self.application.status_history.first().new_status, APPLICATION_STATUS_SHORTLISTED)

    def test_application_detail_view(self):
        response = self.client.get(reverse("adminpanel:application_detail", args=[self.application.pk]))
        self.assertEqual(response.status_code, 200)


class ReviewModerationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin4", "admin4@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin4", password="pass12345")
        self.owner = User.objects.create_user("owner4", "owner4@example.com", "pass12345")
        self.company = Company.objects.create(owner=self.owner, name="Delta Corp")
        self.employer = User.objects.create_user("employer4", "employer4@example.com", "pass12345")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Recruiter",
            location="Remote", description="Hire people.", status=JOB_STATUS_PUBLISHED,
        )
        self.applicant = User.objects.create_user("applicant2", "applicant2@example.com", "pass12345")
        self.application = Application.objects.create(
            job=self.job, applicant=self.applicant, first_name="Rev", last_name="Iewer",
            email="applicant2@example.com", resume=_resume(),
        )
        self.review = CompanyReview.objects.create(
            company=self.company, applicant=self.applicant, application=self.application,
            rating=5, content="Great company to work for, learned a lot.",
        )

    def test_hide_review_via_moderation_form(self):
        url = reverse("adminpanel:review_edit", args=[self.review.pk])
        self.client.post(url, {"is_active": ""})
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_active)

    def test_moderation_never_changes_review_content(self):
        original_content = self.review.content
        url = reverse("adminpanel:review_edit", args=[self.review.pk])
        self.client.post(url, {"is_active": "on"})
        self.review.refresh_from_db()
        self.assertEqual(self.review.content, original_content)


class NotificationBulkTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin5", "admin5@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin5", password="pass12345")
        self.recipient = User.objects.create_user("recipient1", "recipient1@example.com", "pass12345")
        self.notification = Notification.objects.create(recipient=self.recipient, title="Test", message="Hello")

    def test_bulk_mark_read(self):
        url = reverse("adminpanel:notification_list")
        self.client.post(url, {"bulk_action": "mark_read", "selected": [self.notification.pk]})
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)


class HelpCenterAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin6", "admin6@example.com", "pass12345", is_staff=True)
        self.client.login(username="admin6", password="pass12345")
        self.user = User.objects.create_user("fbuser", "fb@example.com", "pass12345")
        Feedback.objects.create(user=self.user, rating=4, message="Nice site")

    def test_feedback_list_and_pagination(self):
        response = self.client.get(reverse("adminpanel:feedback_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("page_obj", response.context)

    def test_global_search(self):
        response = self.client.get(reverse("adminpanel:global_search"), {"q": "fbuser"})
        self.assertEqual(response.status_code, 200)


class CsrfEnforcementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("admin7", "admin7@example.com", "pass12345", is_staff=True)

    def test_delete_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="admin7", password="pass12345")
        target = User.objects.create_user("target7", "target7@example.com", "pass12345")
        url = reverse("adminpanel:user_delete", args=[target.pk])
        response = client.post(url, {})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

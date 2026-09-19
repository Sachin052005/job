from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from applications.models import Application
from companies.models import Company
from core.constants import (
    APPLICATION_STATUS_SHORTLISTED,
    APPLIED_VIA_EASY_APPLY,
    JOB_STATUS_PUBLISHED,
    ROLE_EMPLOYER,
)
from jobs.models import Job

User = get_user_model()


def make_resume():
    return SimpleUploadedFile("resume.pdf", b"%PDF-1.4 fake resume content", content_type="application/pdf")


class ApplicationWorkflowTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme")

        self.seeker = User.objects.create_user(username="seeker", password="pass12345")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Backend Engineer",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )

    def test_seeker_can_apply(self):
        self.client.login(username="seeker", password="pass12345")
        response = self.client.post(
            reverse("applications:apply", kwargs={"job_id": self.job.pk}),
            {"cover_letter": "I am a great fit.", "resume": make_resume()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_duplicate_application_blocked(self):
        Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        self.client.login(username="seeker", password="pass12345")
        response = self.client.get(reverse("applications:apply", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Application.objects.filter(job=self.job, applicant=self.seeker).count(), 1)

    def test_employer_cannot_apply(self):
        self.client.login(username="employer", password="pass12345")
        response = self.client.get(reverse("applications:apply", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_other_employer_cannot_view_applications_for_job(self):
        other = User.objects.create_user(username="other", password="pass12345")
        other.profile.role = ROLE_EMPLOYER
        other.profile.save()
        Company.objects.create(owner=other, name="Other Co")
        Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())

        self.client.login(username="other", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_employer_can_update_application_status(self):
        application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        self.client.login(username="employer", password="pass12345")
        response = self.client.post(
            reverse("applications:update_status", kwargs={"pk": application.pk}),
            {"status": APPLICATION_STATUS_SHORTLISTED},
        )
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, APPLICATION_STATUS_SHORTLISTED)

    def test_applicant_cannot_be_seen_by_unrelated_user(self):
        application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        stranger = User.objects.create_user(username="stranger", password="pass12345")
        self.client.login(username="stranger", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": application.pk}))
        self.assertEqual(response.status_code, 403)


class EasyApplyTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer2", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme Two")

        self.seeker = User.objects.create_user(username="seeker2", password="pass12345")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Python Developer",
            location="Remote", description="Build APIs with Django and Python.",
            skills="Python, Django", status=JOB_STATUS_PUBLISHED,
        )

    def test_incomplete_profile_redirects_to_edit_profile(self):
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:profile_edit"), response.url)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_confirm_blocked_when_profile_incomplete(self):
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.post(reverse("applications:easy_apply_confirm", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def _complete_seeker_profile(self):
        profile = self.seeker.profile
        profile.skills = "Python, Django, MySQL"
        profile.experience_years = 2
        profile.resume = make_resume()
        profile.save()
        return profile

    def test_review_page_shows_match_analysis_when_profile_complete(self):
        self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("match", response.context)
        self.assertIn("Python", response.context["match"]["matched_skills"])

    def test_confirm_creates_application_reusing_profile_resume(self):
        profile = self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.post(reverse("applications:easy_apply_confirm", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get(job=self.job, applicant=self.seeker)
        self.assertEqual(application.applied_via, APPLIED_VIA_EASY_APPLY)
        self.assertEqual(application.resume.name, profile.resume.name)
        self.assertIsNotNone(application.match_snapshot)
        self.assertIn("overall_percent", application.match_snapshot)

    def test_duplicate_easy_apply_prevented(self):
        self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        self.client.post(reverse("applications:easy_apply_confirm", kwargs={"job_id": self.job.pk}))
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Application.objects.filter(job=self.job, applicant=self.seeker).count(), 1)

    def test_manual_apply_flow_still_works_after_easy_apply_refactor(self):
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.post(
            reverse("applications:apply", kwargs={"job_id": self.job.pk}),
            {"cover_letter": "I am a great fit.", "resume": make_resume()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Application.objects.filter(job=self.job, applicant=self.seeker).exists())


class HRCandidateAnalysisTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employer = User.objects.create_user(username="employer3", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme Three")

        self.other_employer = User.objects.create_user(username="employer4", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        Company.objects.create(owner=self.other_employer, name="Acme Four")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Backend Engineer",
            location="Remote", description="Python and Django backend role.",
            skills="Python, Django", status=JOB_STATUS_PUBLISHED,
        )

        self.seeker = User.objects.create_user(username="seeker3", password="pass12345")
        self.seeker.profile.skills = "Python, Django"
        self.seeker.profile.experience_years = 3
        self.seeker.profile.linkedin_url = "https://www.linkedin.com/in/seeker3"
        self.seeker.profile.github_url = "https://github.com/octocat"
        self.seeker.profile.save()
        self.application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())

    def test_other_employer_cannot_view_applicants_list(self):
        self.client.login(username="employer4", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_owning_employer_sees_match_signals_in_applicants_list(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("quick_review", response.context)
        self.assertTrue(response.context["applications"][0].match_snapshot)

    def test_applicant_search_filter(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(
            reverse("applications:for_job", kwargs={"job_id": self.job.pk}), {"keyword": "seeker3"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "seeker3")

    def test_sort_by_match_does_not_error(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(
            reverse("applications:for_job", kwargs={"job_id": self.job.pk}), {"sort": "match"}
        )
        self.assertEqual(response.status_code, 200)

    @patch("services.ats_service.requests.get")
    def test_candidate_detail_shows_match_and_github_analysis(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "job-portal", "description": "Django job portal", "language": "Python", "topics": ["django"]},
        ]
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("match", response.context)
        self.assertEqual(response.context["github_analysis"]["status"], "available")
        self.assertIn("Python", response.context["github_analysis"]["detected_technologies"])
        self.assertEqual(response.context["linkedin_analysis"]["status"], "manual_review")

    @patch("services.ats_service.requests.get")
    def test_candidate_detail_handles_github_failure_gracefully(self, mock_get):
        import requests

        mock_get.side_effect = requests.RequestException("boom")
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["github_analysis"]["status"], "unavailable")

    def test_applicant_cannot_see_employer_match_data(self):
        self.client.login(username="seeker3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_employer_view"])
        self.assertNotIn("match", response.context)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activity.models import StudentActivity
from applications.models import Application, ApplicationStatusHistory, Interview, RecruiterNote
from companies.models import Company
from core.constants import (
    APPLICATION_METHOD_APPLY,
    APPLICATION_METHOD_EASY_APPLY,
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_CHOICES,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_SELECTED,
    APPLICATION_STATUS_SHORTLISTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    APPLIED_VIA_EASY_APPLY,
    APPLIED_VIA_MANUAL,
    JOB_STATUS_PUBLISHED,
    ROLE_EMPLOYER,
)
from jobs.models import Job
from notifications.models import Notification
from notifications.services import notify_new_application, send_application_status_email
from services.skill_match_service import calculate_skill_match

User = get_user_model()


def make_resume(name="resume.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake resume content", content_type="application/pdf")


_APPLY_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@example.com",
    "phone": "9999999999",
    "location": "Bengaluru",
    "current_company": "",
    "current_title": "",
    "experience_years": 0,
    "education_summary": "",
    "skills": "Python, Django",
    "linkedin_url": "https://www.linkedin.com/in/janedoe",
    "github_url": "https://github.com/janedoe",
    "portfolio_url": "https://janedoe.dev",
    "cover_letter": "I am a great fit.",
}


class SkillMatchServiceTests(TestCase):
    """Deterministic, non-AI matching logic (spec sections 5/6/7/19) - no DB needed."""

    def test_exact_case_insensitive_match(self):
        result = calculate_skill_match(["python", "DJANGO"], ["Python", "Django"])
        self.assertEqual(result["percentage"], 100)
        self.assertEqual(result["matched_skills"], ["Python", "Django"])
        self.assertEqual(result["unmatched_skills"], [])

    def test_whitespace_is_trimmed(self):
        result = calculate_skill_match([" Python ", "  Django"], ["Python", "Django"])
        self.assertEqual(result["percentage"], 100)

    def test_known_aliases_are_equivalent(self):
        # "JS" (candidate) vs "JavaScript" (job requirement) both normalize to "JavaScript".
        result = calculate_skill_match(["JS", "git"], ["JavaScript", "Git"])
        self.assertEqual(result["percentage"], 100)
        self.assertIn("JavaScript", result["matched_skills"])

    def test_rest_api_alias_variants_match(self):
        result = calculate_skill_match(["REST APIs"], ["rest api"])
        self.assertEqual(result["percentage"], 100)

    def test_duplicate_skills_are_deduplicated(self):
        result = calculate_skill_match(["Python", "python", "PYTHON"], ["Python"])
        self.assertEqual(result["candidate_skills"], ["Python"])
        self.assertEqual(result["percentage"], 100)

    def test_match_percentage_rounds_to_nearest_whole(self):
        # 4 of 6 required skills = 66.666...% -> rounds to 67.
        candidate = ["Python", "Django", "SQL", "HTML", "CSS", "Git"]
        required = ["Python", "Django", "REST API", "SQL", "Git", "JavaScript"]
        result = calculate_skill_match(candidate, required)
        self.assertEqual(result["percentage"], 67)
        self.assertEqual(result["matched_skills"], ["Python", "Django", "SQL", "Git"])
        self.assertEqual(result["unmatched_skills"], ["REST API", "JavaScript"])

    def test_zero_required_skills_returns_none_percentage(self):
        result = calculate_skill_match(["Python", "Django"], [])
        self.assertIsNone(result["percentage"])
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["unmatched_skills"], [])

    def test_candidate_with_no_skills_is_zero_percent(self):
        result = calculate_skill_match([], ["Python", "Django"])
        self.assertEqual(result["percentage"], 0)
        self.assertEqual(result["unmatched_skills"], ["Python", "Django"])

    def test_extra_candidate_skills_do_not_inflate_percentage(self):
        result = calculate_skill_match(["Python", "Django", "React", "Docker", "AWS"], ["Python", "Django"])
        self.assertEqual(result["percentage"], 100)
        self.assertEqual(result["matched_skills"], ["Python", "Django"])

    def test_comma_separated_string_input_is_accepted(self):
        result = calculate_skill_match("Python, Django, SQL", "Python, Django")
        self.assertEqual(result["percentage"], 100)


class ApplicationWorkflowTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme")

        self.seeker = User.objects.create_user(username="seeker", password="pass12345")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Backend Engineer",
            location="Remote", description="...", skills="Python, Django",
            status=JOB_STATUS_PUBLISHED,
        )

    def _apply_and_confirm(self, payload):
        """Manual Apply is now two steps (spec section 11): POST stages + shows the
        skill-match confirmation, a second POST to apply_confirm actually creates it."""
        staged = self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        return staged, self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))

    def test_seeker_can_apply(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        staged, confirmed = self._apply_and_confirm(payload)
        self.assertEqual(staged.status_code, 200)
        self.assertEqual(confirmed.status_code, 302)
        application = Application.objects.get(job=self.job, applicant=self.seeker)
        self.assertEqual(application.applied_via, APPLIED_VIA_MANUAL)
        self.assertEqual(application.linkedin_url, "https://www.linkedin.com/in/janedoe")

    def test_first_step_does_not_create_application(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        response = self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())
        self.assertContains(response, "Review Your Application")

    def test_confirmation_screen_shows_deterministic_skill_match(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume(), skills="Python, Django")
        response = self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.assertContains(response, "100%")
        self.assertContains(response, "Python")

    def test_apply_requires_professional_links(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        payload.pop("linkedin_url")
        response = self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_confirming_without_staged_data_does_not_create_application(self):
        """Security: hitting Confirm & Apply directly (no prior valid staging step) must not create anything."""
        self.client.login(username="seeker", password="pass12345")
        response = self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_cancel_discards_staged_application(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        response = self.client.post(reverse("applications:apply_cancel", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_duplicate_application_blocked(self):
        Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        self.client.login(username="seeker", password="pass12345")
        response = self.client.get(reverse("applications:apply", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Application.objects.filter(job=self.job, applicant=self.seeker).count(), 1)

    def test_duplicate_application_blocked_at_confirm_step_too(self):
        """Server-side duplicate check must hold even if a stale staged session survives (spec section 20)."""
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        response = self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
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

    def test_employer_can_update_application_status_and_history_and_notification(self):
        application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        self.client.login(username="employer", password="pass12345")
        response = self.client.post(
            reverse("applications:update_status", kwargs={"pk": application.pk}),
            {"status": APPLICATION_STATUS_SHORTLISTED},
        )
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, APPLICATION_STATUS_SHORTLISTED)
        self.assertEqual(ApplicationStatusHistory.objects.filter(application=application).count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.seeker, application=application).exists())

    def test_applicant_cannot_be_seen_by_unrelated_user(self):
        application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())
        stranger = User.objects.create_user(username="stranger", password="pass12345")
        self.client.login(username="stranger", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": application.pk}))
        self.assertEqual(response.status_code, 403)

    def test_manual_application_keeps_submitted_values_not_profile_values(self):
        """spec section 12: the application snapshot must contain what was submitted,
        even if it differs from the profile."""
        self.seeker.profile.phone = "9876543210"
        self.seeker.profile.save()
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume(), phone="9876500000")
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        application = Application.objects.get(job=self.job, applicant=self.seeker)
        self.assertEqual(application.phone, "9876500000")
        self.seeker.profile.refresh_from_db()
        self.assertEqual(self.seeker.profile.phone, "9876543210")

    def test_manual_application_stores_match_snapshot(self):
        self.client.login(username="seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume(), skills="Python, Django, SQL, HTML, CSS, Git")
        job = Job.objects.create(
            employer=self.employer, company=self.company, title="Full Stack Role",
            location="Remote", description="...", skills="Python, Django, REST API, SQL, Git, JavaScript",
            status=JOB_STATUS_PUBLISHED,
        )
        self.client.post(reverse("applications:apply", kwargs={"job_id": job.pk}), payload)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": job.pk}))
        application = Application.objects.get(job=job, applicant=self.seeker)
        self.assertEqual(application.match_percentage, 67)
        self.assertEqual(application.matched_skills, ["Python", "Django", "SQL", "Git"])
        self.assertEqual(application.unmatched_skills, ["REST API", "JavaScript"])
        self.assertEqual(application.job_skills_snapshot, ["Python", "Django", "REST API", "SQL", "Git", "JavaScript"])


class ApplicationMethodEnforcementTests(TestCase):
    """Backend must enforce application_method, not just hide buttons (spec section 13)."""

    def setUp(self):
        self.employer = User.objects.create_user(username="employer5", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme Five")
        self.seeker = User.objects.create_user(username="seeker5", password="pass12345")

    def test_apply_url_rejected_when_easy_apply_only(self):
        job = Job.objects.create(
            employer=self.employer, company=self.company, title="Role",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
            application_method=APPLICATION_METHOD_EASY_APPLY,
        )
        self.client.login(username="seeker5", password="pass12345")
        response = self.client.get(reverse("applications:apply", kwargs={"job_id": job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.filter(job=job).exists())

    def test_easy_apply_url_rejected_when_apply_only(self):
        job = Job.objects.create(
            employer=self.employer, company=self.company, title="Role",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
            application_method=APPLICATION_METHOD_APPLY,
        )
        self.client.login(username="seeker5", password="pass12345")
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.filter(job=job).exists())


class EasyApplyTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(username="employer2", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Acme Two")

        self.seeker = User.objects.create_user(
            username="seeker2", password="pass12345", first_name="Seeker", email="seeker2@example.com"
        )

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Python Developer",
            location="Remote", description="Build APIs with Django and Python.",
            skills="Python, Django, REST API, SQL, Git, JavaScript", status=JOB_STATUS_PUBLISHED,
        )

    def test_incomplete_profile_redirects_to_edit_profile(self):
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:profile_edit"), response.url)
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_missing_fields_are_listed_on_the_redirect_message(self):
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.get(
            reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}), follow=True
        )
        messages = [str(m) for m in response.context["messages"]]
        combined = " ".join(messages)
        self.assertIn("Resume", combined)
        self.assertIn("Skills", combined)

    def _complete_seeker_profile(self):
        profile = self.seeker.profile
        profile.skills = "Python, Django, SQL, HTML, CSS, Git"
        profile.experience_years = 2
        profile.resume = make_resume()
        profile.phone = "9876543210"
        profile.location = "Salem, Tamil Nadu"
        profile.linkedin_url = "https://www.linkedin.com/in/seeker2"
        profile.github_url = "https://github.com/seeker2"
        profile.save()
        return profile

    def test_profile_ready_once_all_required_fields_present(self):
        self._complete_seeker_profile()
        self.assertTrue(self.seeker.profile.is_easy_apply_ready())

    def test_review_page_loads_profile_snapshot_and_match(self):
        self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["snapshot"]["email"], "seeker2@example.com")
        self.assertEqual(response.context["snapshot"]["linkedin_url"], "https://www.linkedin.com/in/seeker2")
        self.assertEqual(response.context["match"]["percentage"], 67)
        self.assertContains(response, "67%")
        self.assertContains(response, "REST API")

    def test_get_does_not_create_application(self):
        self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertFalse(Application.objects.filter(job=self.job, applicant=self.seeker).exists())

    def test_confirm_creates_application_reusing_profile_resume_and_match_snapshot(self):
        profile = self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        response = self.client.post(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get(job=self.job, applicant=self.seeker)
        self.assertEqual(application.applied_via, APPLIED_VIA_EASY_APPLY)
        self.assertEqual(application.resume.name, profile.resume.name)
        self.assertEqual(application.match_percentage, 67)
        self.assertEqual(application.matched_skills, ["Python", "Django", "SQL", "Git"])
        self.assertEqual(application.unmatched_skills, ["REST API", "JavaScript"])
        # Profile.effective_skills_list() returns an alphabetically sorted set (by design).
        self.assertEqual(application.student_skills_snapshot, ["CSS", "Django", "Git", "HTML", "Python", "SQL"])

    def test_duplicate_easy_apply_prevented(self):
        self._complete_seeker_profile()
        self.client.login(username="seeker2", password="pass12345")
        self.client.post(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        response = self.client.get(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Application.objects.filter(job=self.job, applicant=self.seeker).count(), 1)

    def test_manual_apply_flow_still_works_after_easy_apply_refactor(self):
        self.client.login(username="seeker2", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        staged = self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.assertEqual(staged.status_code, 200)
        confirmed = self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        self.assertEqual(confirmed.status_code, 302)
        self.assertTrue(Application.objects.filter(job=self.job, applicant=self.seeker).exists())


class HRApplicationsListTests(TestCase):
    def setUp(self):
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
            skills="Python, Django, REST API, SQL, Git, JavaScript", status=JOB_STATUS_PUBLISHED,
        )

        self.seeker = User.objects.create_user(username="seeker3", password="pass12345")
        self.application = Application.objects.create(
            job=self.job, applicant=self.seeker, resume=make_resume(),
            first_name="Seeker", last_name="Three", skills="Python, Django, SQL, HTML, CSS, Git",
            linkedin_url="https://www.linkedin.com/in/seeker3",
            github_url="https://github.com/seeker3",
            applied_via=APPLIED_VIA_EASY_APPLY,
        )
        match = calculate_skill_match(self.application.skills, self.job.skills)
        self.application.apply_skill_match(match)
        self.application.save()

    def test_other_employer_cannot_view_applicants_list(self):
        self.client.login(username="employer4", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 403)

    def test_owning_employer_sees_applicants_list(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seeker")

    def test_owning_employer_sees_stored_skill_match_not_recalculated(self):
        """spec section 14: HR sees the frozen match snapshot, not a live recomputation."""
        self.client.login(username="employer3", password="pass12345")
        # Change the candidate's live profile skills after applying - the stored snapshot must not change.
        self.seeker.profile.skills = "Only Cobol"
        self.seeker.profile.save()
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        self.assertContains(response, "67%")

    def test_applicant_search_filter(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(
            reverse("applications:for_job", kwargs={"job_id": self.job.pk}), {"keyword": "seeker3"}
        )
        self.assertEqual(response.status_code, 200)

    def test_candidate_detail_shows_snapshot_links(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_employer_view"])
        self.assertContains(response, "github.com/seeker3")

    def test_candidate_detail_shows_match_snapshot(self):
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertContains(response, "67%")
        self.assertContains(response, "REST API")

    def test_no_ranking_or_ai_language_in_applicants_list(self):
        """spec sections 16/17: no AI scoring, no ranking/best-candidate labels."""
        self.client.login(username="employer3", password="pass12345")
        response = self.client.get(reverse("applications:for_job", kwargs={"job_id": self.job.pk}))
        content = response.content.decode()
        for forbidden in ("Best Candidate", "Recommended Candidate", "#1 Candidate", "AI Match", "AI Score"):
            self.assertNotIn(forbidden, content)

    def test_applicant_cannot_see_employer_only_flag(self):
        self.client.login(username="seeker3", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_employer_view"])


class NotificationRecipientTests(TestCase):
    """Application submission must notify the responsible recruiter, never
    the applicant; a status change must notify the applicant, never
    whoever made the change (HR or admin)."""

    def setUp(self):
        self.employer = User.objects.create_user(username="notif_employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Notif Co")

        self.other_employer = User.objects.create_user(username="notif_other_employer", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        Company.objects.create(owner=self.other_employer, name="Other Notif Co")

        self.seeker = User.objects.create_user(
            username="notif_seeker", password="pass12345", first_name="Priya", email="priya@example.com"
        )
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Python Django Developer",
            location="Remote", description="Build APIs.", status=JOB_STATUS_PUBLISHED,
        )

    def _apply(self):
        return Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())

    def _set_status(self, application, status, username="notif_employer"):
        self.client.login(username=username, password="pass12345")
        response = self.client.post(
            reverse("applications:update_status", kwargs={"pk": application.pk}), {"status": status}
        )
        self.client.logout()
        return response

    # -- 11/12/13/14: submitting an application notifies HR, not the student --

    def test_manual_apply_notifies_hr_not_student(self):
        self.client.login(username="notif_seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        application = Application.objects.get(job=self.job, applicant=self.seeker)

        hr_notification = Notification.objects.filter(recipient=self.employer, application=application).first()
        self.assertIsNotNone(hr_notification)
        self.assertEqual(hr_notification.title, "New Job Application")
        self.assertFalse(Notification.objects.filter(recipient=self.seeker, application=application).exists())

    def test_easy_apply_notifies_hr_not_student(self):
        profile = self.seeker.profile
        profile.skills = "Python, Django"
        profile.experience_years = 2
        profile.resume = make_resume()
        profile.phone = "9876543210"
        profile.location = "Chennai"
        profile.linkedin_url = "https://www.linkedin.com/in/notifseeker"
        profile.github_url = "https://github.com/notifseeker"
        profile.save()

        self.client.login(username="notif_seeker", password="pass12345")
        self.client.post(reverse("applications:easy_apply_review", kwargs={"job_id": self.job.pk}))
        application = Application.objects.get(job=self.job, applicant=self.seeker)

        self.assertTrue(Notification.objects.filter(recipient=self.employer, application=application).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.seeker, application=application).exists())

    def test_correct_hr_receives_notification_not_unrelated_employer(self):
        self.client.login(username="notif_seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        application = Application.objects.get(job=self.job, applicant=self.seeker)

        self.assertFalse(
            Notification.objects.filter(recipient=self.other_employer, application=application).exists()
        )

    # -- 15-19: every HR status transition notifies the student -----------

    def test_status_progression_each_step_notifies_student_exactly_once(self):
        application = self._apply()
        status_labels = dict(APPLICATION_STATUS_CHOICES)
        progression = [
            APPLICATION_STATUS_UNDER_REVIEW,
            APPLICATION_STATUS_SHORTLISTED,
            APPLICATION_STATUS_INTERVIEW,
            APPLICATION_STATUS_HIRED,
        ]
        for status in progression:
            Notification.objects.filter(recipient=self.seeker).delete()
            self._set_status(application, status)
            notifications = Notification.objects.filter(recipient=self.seeker, application=application)
            self.assertEqual(notifications.count(), 1, f"expected exactly one notification for {status}")
            self.assertIn(status_labels[status], notifications.first().message)

    def test_interview_to_rejected_notifies_student(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_INTERVIEW)
        Notification.objects.filter(recipient=self.seeker).delete()
        self._set_status(application, APPLICATION_STATUS_REJECTED)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.seeker, application=application, message__icontains="Rejected"
            ).exists()
        )

    # -- 20/21: no status change, no notification; no duplicates ----------

    def test_saving_same_status_does_not_notify(self):
        application = self._apply()
        self._set_status(application, application.status)
        self.assertFalse(Notification.objects.filter(recipient=self.seeker, application=application).exists())

    def test_repeated_identical_status_post_does_not_duplicate_notification(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self.assertEqual(
            Notification.objects.filter(recipient=self.seeker, application=application).count(), 1
        )

    # -- 22: HR never notifies itself --------------------------------------

    def test_hr_does_not_receive_notification_for_own_status_update(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self.assertFalse(Notification.objects.filter(recipient=self.employer, application=application).exists())

    # -- 23: admin panel status change also notifies the student ----------

    def test_admin_status_update_notifies_student(self):
        application = self._apply()
        User.objects.create_user("notif_admin", "notif_admin@example.com", "pass12345", is_staff=True)
        self.client.login(username="notif_admin", password="pass12345")
        self.client.post(
            reverse("adminpanel:application_status", kwargs={"pk": application.pk}),
            {"status": APPLICATION_STATUS_SHORTLISTED},
        )
        self.assertTrue(Notification.objects.filter(recipient=self.seeker, application=application).exists())

    # -- 24: unread count belongs to the correct user ----------------------

    def test_unread_notification_count_belongs_to_correct_user(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)

        self.client.login(username="notif_seeker", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["unread_notification_count"], 1)
        self.client.logout()

        self.client.login(username="notif_employer", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["unread_notification_count"], 0)

    # -- 25: notification links to the correct application ----------------

    def test_notification_links_to_correct_application(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        notification = Notification.objects.get(recipient=self.seeker, application=application)
        self.assertEqual(
            notification.get_absolute_url(), reverse("applications:detail", kwargs={"pk": application.pk})
        )

    # -- 26/27: notifications are never visible to anyone but the recipient --

    def test_student_cannot_open_hr_notification(self):
        application = self._apply()
        hr_notification = notify_new_application(application)
        self.client.login(username="notif_seeker", password="pass12345")
        response = self.client.post(reverse("notifications:open", kwargs={"pk": hr_notification.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_hr_cannot_open_unrelated_hr_notification(self):
        application = self._apply()
        hr_notification = notify_new_application(application)
        self.client.login(username="notif_other_employer", password="pass12345")
        response = self.client.post(reverse("notifications:open", kwargs={"pk": hr_notification.pk}))
        self.assertEqual(response.status_code, 404)

    def test_notification_list_shows_only_own_notifications(self):
        application = self._apply()
        notify_new_application(application)  # recipient = self.employer

        self.client.login(username="notif_seeker", password="pass12345")
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(list(response.context["notifications"]), [])


class ApplicationStatusEmailTests(TestCase):
    """HR changing an application's status must email the student with
    status-specific content (spec sections 1-9, 14-19), routed through the
    single Application.record_status_change() choke point (spec sections
    11-12), never duplicated, and never able to break the status update
    itself even if sending fails (spec sections 10, 19-21)."""

    def setUp(self):
        self.employer = User.objects.create_user(username="mail_employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Mail Co")

        self.seeker = User.objects.create_user(
            username="mail_seeker", password="pass12345", email="seeker@example.com",
        )
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Python Django Developer",
            location="Remote", description="Build APIs.", status=JOB_STATUS_PUBLISHED,
        )

    def _apply(self):
        return Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())

    def _set_status(self, application, status):
        self.client.login(username="mail_employer", password="pass12345")
        response = self.client.post(
            reverse("applications:update_status", kwargs={"pk": application.pk}), {"status": status}
        )
        self.client.logout()
        return response

    def test_manual_apply_sends_applied_confirmation_email(self):
        self.client.login(username="mail_seeker", password="pass12345")
        payload = dict(_APPLY_PAYLOAD, resume=make_resume())
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))
        application = Application.objects.get(job=self.job, applicant=self.seeker)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn(self.job.title, sent.subject)
        self.assertIn(self.company.name, sent.subject)
        self.assertEqual(sent.to, [self.seeker.email])
        self.assertIn("successfully submitted", sent.body)

    def test_under_review_email_is_reassuring_and_does_not_claim_shortlisted(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_UNDER_REVIEW)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, [self.seeker.email])
        self.assertIn("Under Review", sent.subject)
        self.assertIn("currently reviewing", sent.body)
        self.assertNotIn("shortlisted", sent.body.lower())

    def test_shortlisted_email_congratulates_without_promising_interview(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)

        sent = mail.outbox[0]
        self.assertIn("Shortlisted", sent.subject)
        self.assertIn("Congratulations", sent.body)
        self.assertIn(self.job.title, sent.body)
        self.assertNotIn("interview has been scheduled", sent.body.lower())

    def test_interview_email_uses_real_interview_details_when_scheduled(self):
        application = self._apply()
        interview = Interview.objects.create(
            application=application, interview_type="video",
            scheduled_at="2026-10-01T10:00:00Z", meeting_link="https://meet.example.com/abc",
        )
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_INTERVIEW)

        sent = mail.outbox[0]
        self.assertIn(self.job.title, sent.subject)
        self.assertIn(interview.meeting_link, sent.body)
        self.assertNotIn("shortly with the interview date", sent.body)

    def test_interview_email_does_not_invent_details_when_none_scheduled(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_INTERVIEW)

        sent = mail.outbox[0]
        self.assertIn("contact you shortly", sent.body)

    def test_selected_and_hired_are_distinct_emails(self):
        application = self._apply()
        self._set_status(application, APPLICATION_STATUS_SELECTED)
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_HIRED)

        sent = mail.outbox[0]
        self.assertIn("Hired", sent.subject)
        self.assertIn("hired", sent.body.lower())

    def test_selected_email_does_not_say_hired(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_SELECTED)

        sent = mail.outbox[0]
        self.assertIn("Selected", sent.subject)
        self.assertNotIn("hired", sent.body.lower())

    def test_rejected_email_is_respectful_and_links_to_jobs_page(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_REJECTED)

        sent = mail.outbox[0]
        self.assertIn("Thank you for your interest", sent.body)
        self.assertIn("Explore More Jobs", sent.body)
        self.assertIn(reverse("jobs:list"), sent.body)
        self.assertNotIn("unfortunately", sent.body.lower())

    def test_same_status_save_does_not_send_email(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, application.status)
        self.assertEqual(len(mail.outbox), 0)

    def test_repeated_identical_status_post_does_not_duplicate_email(self):
        application = self._apply()
        mail.outbox.clear()
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_failure_does_not_block_status_update(self):
        application = self._apply()
        with patch("notifications.services.send_mail", side_effect=Exception("SMTP down")):
            response = self._set_status(application, APPLICATION_STATUS_SHORTLISTED)
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, APPLICATION_STATUS_SHORTLISTED)
        self.assertTrue(
            ApplicationStatusHistory.objects.filter(application=application, new_status=APPLICATION_STATUS_SHORTLISTED).exists()
        )

    def test_missing_recipient_email_skips_send_without_raising(self):
        self.seeker.email = ""
        self.seeker.save()
        application = self._apply()
        application.email = ""
        application.save(update_fields=["email"])
        mail.outbox.clear()

        sent = send_application_status_email(application, APPLICATION_STATUS_APPLIED, APPLICATION_STATUS_SHORTLISTED)

        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_falls_back_to_application_snapshot_email_when_account_email_missing(self):
        self.seeker.email = ""
        self.seeker.save()
        application = self._apply()
        application.email = "snapshot@example.com"
        application.save(update_fields=["email"])
        mail.outbox.clear()

        self._set_status(application, APPLICATION_STATUS_SHORTLISTED)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["snapshot@example.com"])


class InterviewManagementPageTests(TestCase):
    """Interview scheduling/management lives on its own dedicated HR page,
    not embedded in the application/candidate review page (spec: remove the
    unwanted Interviews block from candidate review without breaking real
    interview scheduling)."""

    def setUp(self):
        self.employer = User.objects.create_user(username="iv_employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Interview Co")
        self.seeker = User.objects.create_user(username="iv_seeker", password="pass12345", email="ivseeker@example.com")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Backend Developer",
            location="Remote", description="Build APIs.", status=JOB_STATUS_PUBLISHED,
        )
        self.application = Application.objects.create(job=self.job, applicant=self.seeker, resume=make_resume())

    def test_application_detail_no_longer_embeds_interview_scheduling(self):
        self.client.login(username="iv_employer", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertNotContains(response, "No interviews scheduled yet.")
        self.assertContains(response, "Manage Interviews")

    def test_interview_list_page_lists_applications_and_schedules_interview(self):
        self.client.login(username="iv_employer", password="pass12345")
        response = self.client.get(reverse("applications:interview_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.application.full_name())

        response = self.client.post(
            reverse("applications:interview_add", kwargs={"pk": self.application.pk}),
            {
                "interview_type": "video", "scheduled_at": "2026-11-01T10:00",
                "location": "", "meeting_link": "", "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Interview.objects.filter(application=self.application).exists())

    def test_other_employer_cannot_see_interviews_for_a_different_company(self):
        other = User.objects.create_user(username="iv_other", password="pass12345")
        other.profile.role = ROLE_EMPLOYER
        other.profile.save()
        Company.objects.create(owner=other, name="Other Interview Co")
        Interview.objects.create(
            application=self.application, interview_type="phone", scheduled_at="2026-11-01T10:00:00Z",
        )

        self.client.login(username="iv_other", password="pass12345")
        response = self.client.get(reverse("applications:interview_list"))
        self.assertNotContains(response, self.application.full_name())


def make_real_resume(name="resume.pdf"):
    """A genuinely parseable PDF (unlike make_resume()'s magic-bytes-only
    fake) - needed for tests that exercise the actual ATS pipeline rather
    than just the upload validator."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "Jane Doe\njane@example.com\nSKILLS\nPython, Django, REST API, MySQL\nEDUCATION\nB.Tech, 2024",
        fontsize=10,
    )
    data = doc.tobytes()
    doc.close()
    return SimpleUploadedFile(name, data, content_type="application/pdf")


class ApplicationATSProcessingTests(TestCase):
    """spec: Application Created -> ATS Processing -> ATS Result Stored,
    and ATS failure must never break a valid application."""

    def setUp(self):
        self.seeker = User.objects.create_user(username="ats_seeker", password="pass12345")
        self.employer = User.objects.create_user(username="ats_employer", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="ATS Test Co")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Python Developer",
            location="Bengaluru", description="Django REST API role",
            skills="Python, Django, REST API, MySQL", status=JOB_STATUS_PUBLISHED,
        )
        self.client.login(username="ats_seeker", password="pass12345")

    def _apply_with(self, resume_file):
        payload = dict(_APPLY_PAYLOAD, resume=resume_file)
        self.client.post(reverse("applications:apply", kwargs={"job_id": self.job.pk}), payload)
        return self.client.post(reverse("applications:apply_confirm", kwargs={"job_id": self.job.pk}))

    def test_ats_processing_succeeds_with_a_real_parseable_resume(self):
        self._apply_with(make_real_resume())
        application = Application.objects.get(job=self.job, applicant=self.seeker)
        self.assertEqual(application.ats_status, "complete")
        self.assertIsNotNone(application.ats_score)
        self.assertIn("required_skills_percent", application.ats_breakdown)

    def test_application_still_created_when_resume_cannot_be_parsed(self):
        """The existing make_resume() fixture is magic-bytes-only, not a
        real PDF - PyMuPDF cannot parse it, so ATS processing must fail
        gracefully while the application itself remains valid."""
        self._apply_with(make_resume())
        application = Application.objects.filter(job=self.job, applicant=self.seeker).first()
        self.assertIsNotNone(application, "application must exist even when ATS parsing fails")
        self.assertEqual(application.ats_status, "failed")
        self.assertTrue(application.ats_error)
        self.assertIsNone(application.ats_score)


class RecruiterATSSecurityTests(TestCase):
    """IDOR protection for resume access, recruiter notes, and interviews -
    only the owning company's recruiter may reach these."""

    def setUp(self):
        self.seeker = User.objects.create_user(username="sec_seeker", password="pass12345")
        self.owner_employer = User.objects.create_user(username="sec_owner", password="pass12345")
        self.owner_employer.profile.role = ROLE_EMPLOYER
        self.owner_employer.profile.save()
        self.other_employer = User.objects.create_user(username="sec_other", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        self.company = Company.objects.create(owner=self.owner_employer, name="Owner Co")
        Company.objects.create(owner=self.other_employer, name="Other Co")
        self.job = Job.objects.create(
            employer=self.owner_employer, company=self.company, title="Dev",
            location="Remote", description="...", skills="Python", status=JOB_STATUS_PUBLISHED,
        )
        self.application = Application.objects.create(
            job=self.job, applicant=self.seeker, resume=make_real_resume(), skills="Python",
        )

    def test_other_companys_recruiter_cannot_view_application(self):
        self.client.login(username="sec_other", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertEqual(response.status_code, 403)

    def test_other_companys_recruiter_cannot_view_resume(self):
        self.client.login(username="sec_other", password="pass12345")
        response = self.client.get(reverse("applications:resume", kwargs={"pk": self.application.pk, "mode": "view"}))
        self.assertEqual(response.status_code, 403)

    def test_other_companys_recruiter_cannot_add_note(self):
        self.client.login(username="sec_other", password="pass12345")
        response = self.client.post(
            reverse("applications:note_add", kwargs={"pk": self.application.pk}), {"text": "sneaky note"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RecruiterNote.objects.filter(application=self.application).exists())

    def test_owning_recruiter_can_view_and_download_resume_and_it_is_tracked(self):
        self.client.login(username="sec_owner", password="pass12345")
        response = self.client.get(reverse("applications:resume", kwargs={"pk": self.application.pk, "mode": "view"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentActivity.objects.filter(student=self.seeker, event_type="resume_view").count(), 1)

    def test_applicant_can_view_own_resume_without_being_tracked_as_recruiter_action(self):
        self.client.login(username="sec_seeker", password="pass12345")
        response = self.client.get(reverse("applications:resume", kwargs={"pk": self.application.pk, "mode": "view"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentActivity.objects.filter(student=self.seeker, event_type="resume_view").count(), 0)

    def test_recruiter_note_hidden_from_applicant(self):
        RecruiterNote.objects.create(application=self.application, author=self.owner_employer, text="Secret note")
        self.client.login(username="sec_seeker", password="pass12345")
        response = self.client.get(reverse("applications:detail", kwargs={"pk": self.application.pk}))
        self.assertNotContains(response, "Secret note")

    def test_interview_scheduling_notifies_candidate_and_logs_activity(self):
        self.client.login(username="sec_owner", password="pass12345")
        response = self.client.post(
            reverse("applications:interview_add", kwargs={"pk": self.application.pk}),
            {
                "interview_type": "technical", "scheduled_at": "2026-10-05T10:00",
                "location": "", "meeting_link": "https://meet.example.com/x", "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Interview.objects.filter(application=self.application).exists())
        self.assertEqual(StudentActivity.objects.filter(student=self.seeker, event_type="interview").count(), 1)
        self.assertTrue(
            Notification.objects.filter(recipient=self.seeker, title="Interview scheduled").exists()
        )

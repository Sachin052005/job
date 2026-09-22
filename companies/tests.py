import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import Profile
from applications.models import Application
from companies.models import Company, CompanyFollow, CompanyOffice, CompanyProductService, CompanyReview, CompanySalary
from core.constants import (
    APPLICATION_STATUS_APPLIED,
    APPLICATION_STATUS_HIRED,
    APPLICATION_STATUS_INTERVIEW,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_SHORTLISTED,
    JOB_STATUS_PUBLISHED,
    ROLE_EMPLOYER,
    ROLE_JOB_SEEKER,
)
from jobs.models import Job

User = get_user_model()


def make_resume(name="resume.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake resume content", content_type="application/pdf")


def make_image(name="review.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="green").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


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


class CompanyFollowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="companyowner", password="pass12345")
        self.owner.profile.role = ROLE_EMPLOYER
        self.owner.profile.save()
        self.company = Company.objects.create(owner=self.owner, name="Followable Co")

        self.seeker = User.objects.create_user(username="follower", password="pass12345")
        self.client.login(username="follower", password="pass12345")

    def test_follow_then_unfollow(self):
        url = reverse("companies:follow_toggle", kwargs={"slug": self.company.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CompanyFollow.objects.filter(user=self.seeker, company=self.company).exists())

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CompanyFollow.objects.filter(user=self.seeker, company=self.company).exists())

    def test_duplicate_follow_prevented(self):
        CompanyFollow.objects.create(user=self.seeker, company=self.company)
        with self.assertRaises(Exception):
            CompanyFollow.objects.create(user=self.seeker, company=self.company)

    def test_followed_companies_empty_state(self):
        response = self.client.get(reverse("companies:followed"))
        self.assertContains(response, "You aren't following any companies yet.")

    def test_login_required_to_follow(self):
        self.client.logout()
        response = self.client.post(reverse("companies:follow_toggle", kwargs={"slug": self.company.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)


class CompanyDetailTabsTests(TestCase):
    """spec sections 1/24: exactly seven tabs, Interview Questions/Benefits gone."""

    def setUp(self):
        owner = User.objects.create_user(username="tabowner", password="pass12345")
        owner.profile.role = ROLE_EMPLOYER
        owner.profile.save()
        self.company = Company.objects.create(owner=owner, name="Tabbed Co")

    def test_final_tabs_render_without_error(self):
        for tab in ["overview", "jobs", "reviews", "salaries", "culture", "locations", "products"]:
            response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": tab})
            self.assertEqual(response.status_code, 200, f"tab={tab}")

    def test_tab_navigation_has_exactly_the_final_seven_tabs(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}))
        tab_keys = [key for key, _label in response.context["tabs"]]
        self.assertEqual(
            tab_keys, ["overview", "jobs", "reviews", "salaries", "culture", "locations", "products"]
        )

    def test_interview_questions_tab_not_in_navigation(self):
        # Checks the removed company-profile tab specifically - deliberately does not
        # assert on the substring "Interview Questions" alone, since the site's
        # unrelated Help Center interview-prep links ("HR Interview Questions") must
        # stay untouched (spec section 1: only the company-profile tab is removed).
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}))
        self.assertNotContains(response, "tab=interview_questions")
        tab_keys = [key for key, _label in response.context["tabs"]]
        self.assertNotIn("interview_questions", tab_keys)

    def test_benefits_tab_not_in_navigation(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}))
        self.assertNotContains(response, "tab=benefits")
        tab_keys = [key for key, _label in response.context["tabs"]]
        self.assertNotIn("benefits", tab_keys)


class CompanyManagementTests(TestCase):
    """spec sections 2-8/27-29: HR enters Overview/Salaries/Culture/Locations/Products,
    and it shows up on the public/student profile untouched."""

    def setUp(self):
        self.employer = User.objects.create_user(username="hr1", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="ABC Technologies")

        self.other_employer = User.objects.create_user(username="hr2", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        Company.objects.create(owner=self.other_employer, name="Other Co")

        self.seeker = User.objects.create_user(username="student1", password="pass12345")

    def test_manage_page_requires_login_and_role(self):
        response = self.client.get(reverse("companies:manage"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="student1", password="pass12345")
        response = self.client.get(reverse("companies:manage"))
        self.assertEqual(response.status_code, 403)

    def test_hr_can_update_overview_and_culture(self):
        self.client.login(username="hr1", password="pass12345")
        response = self.client.post(
            reverse("companies:manage"),
            {
                "description": "ABC Technologies is a software development company.",
                "culture": "We value collaboration and continuous learning.",
                "work_environment": "Hybrid, flexible hours.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.description, "ABC Technologies is a software development company.")
        self.assertEqual(self.company.culture, "We value collaboration and continuous learning.")

    def test_overview_appears_on_public_profile(self):
        self.company.description = "ABC Technologies is a software development company."
        self.company.save()
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}))
        self.assertContains(response, "ABC Technologies is a software development company.")

    def test_overview_empty_state(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "overview"})
        self.assertContains(response, "No overview information provided yet.")

    def test_culture_appears_on_public_profile_and_empty_state(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "culture"})
        self.assertContains(response, "No culture information provided yet.")

        self.company.culture = "We move fast and support each other."
        self.company.save()
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "culture"})
        self.assertContains(response, "We move fast and support each other.")

    def test_hr_can_add_salary_information(self):
        self.client.login(username="hr1", password="pass12345")
        response = self.client.post(
            reverse("companies:salary_add"),
            {
                "role": "Software Engineer",
                "salary_range": "₹4 LPA - ₹8 LPA",
                "experience_level": "junior",
                "employment_type": "full_time",
                "location": "Chennai",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        salary = CompanySalary.objects.get(company=self.company)
        self.assertEqual(salary.role, "Software Engineer")

    def test_other_employer_cannot_add_salary_to_another_company(self):
        salary = CompanySalary.objects.create(company=self.company, role="Dev", salary_range="4-8 LPA")
        self.client.login(username="hr2", password="pass12345")
        response = self.client.get(reverse("companies:salary_edit", kwargs={"pk": salary.pk}))
        self.assertEqual(response.status_code, 404)

    def test_salary_appears_on_public_profile(self):
        CompanySalary.objects.create(
            company=self.company, role="Software Engineer", salary_range="₹4 LPA - ₹8 LPA",
        )
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "salaries"})
        self.assertContains(response, "Software Engineer")
        self.assertContains(response, "₹4 LPA - ₹8 LPA")

    def test_salaries_empty_state(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "salaries"})
        self.assertContains(response, "No salary information provided yet.")

    def test_hr_can_add_branch_location(self):
        self.client.login(username="hr1", password="pass12345")
        response = self.client.post(
            reverse("companies:location_add"),
            {
                "name": "Chennai Office",
                "office_type": "branch",
                "address": "123 Main Street",
                "city": "Chennai",
                "state": "Tamil Nadu",
                "country": "India",
                "pincode": "600001",
                "contact_phone": "",
                "contact_email": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        office = CompanyOffice.objects.get(company=self.company)
        self.assertEqual(office.city, "Chennai")

    def test_hr_can_edit_and_delete_branch_location(self):
        office = CompanyOffice.objects.create(company=self.company, name="Old Office", city="Pune")
        self.client.login(username="hr1", password="pass12345")

        response = self.client.post(
            reverse("companies:location_edit", kwargs={"pk": office.pk}),
            {"name": "New Office", "office_type": "branch", "address": "", "city": "Mumbai", "state": "",
             "country": "India", "pincode": "", "contact_phone": "", "contact_email": ""},
        )
        self.assertEqual(response.status_code, 302)
        office.refresh_from_db()
        self.assertEqual(office.city, "Mumbai")

        response = self.client.post(reverse("companies:location_delete", kwargs={"pk": office.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CompanyOffice.objects.filter(pk=office.pk).exists())

    def test_multiple_branches_all_display(self):
        for city in ["Chennai", "Bangalore", "Hyderabad"]:
            CompanyOffice.objects.create(company=self.company, name=f"{city} Office", city=city)
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "locations"})
        for city in ["Chennai", "Bangalore", "Hyderabad"]:
            self.assertContains(response, f"{city} Office")

    def test_locations_empty_state(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "locations"})
        self.assertContains(response, "No branch locations provided yet.")

    def test_hr_can_add_product_and_service(self):
        self.client.login(username="hr1", password="pass12345")
        response = self.client.post(
            reverse("companies:product_add"),
            {"item_type": "product", "name": "NammaCloud", "description": "Cloud infrastructure platform.", "link": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CompanyProductService.objects.filter(company=self.company, name="NammaCloud").exists())

    def test_products_and_services_appear_on_public_profile(self):
        CompanyProductService.objects.create(
            company=self.company, item_type=CompanyProductService.TYPE_PRODUCT,
            name="NammaCloud", description="Cloud infrastructure platform.",
        )
        CompanyProductService.objects.create(
            company=self.company, item_type=CompanyProductService.TYPE_SERVICE,
            name="Software Development", description="Enterprise application development services.",
        )
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "products"})
        self.assertContains(response, "NammaCloud")
        self.assertContains(response, "Software Development")

    def test_products_empty_state(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "products"})
        self.assertContains(response, "No products or services information provided yet.")

    def test_unauthorized_user_cannot_edit_company_management_sections(self):
        self.client.login(username="student1", password="pass12345")
        for url in [
            reverse("companies:manage"),
            reverse("companies:salary_add"),
            reverse("companies:location_add"),
            reverse("companies:product_add"),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, url)

    def test_unauthenticated_user_cannot_edit_company_management_sections(self):
        for url in [reverse("companies:manage"), reverse("companies:salary_add")]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)


class CompanyReviewEligibilityTests(TestCase):
    """spec sections 9-11/23/32: review is gated on the project's actual Hired status."""

    def setUp(self):
        self.employer = User.objects.create_user(username="hremp", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Review Co")

        self.seeker = User.objects.create_user(username="reviewer1", password="pass12345")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Engineer",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )
        self.client.login(username="reviewer1", password="pass12345")

    def _apply_with_status(self, status):
        return Application.objects.create(
            job=self.job, applicant=self.seeker, resume=make_resume(), status=status,
        )

    def _review_url(self):
        return reverse("companies:review_add", kwargs={"slug": self.company.slug})

    def test_cannot_review_with_no_application_at_all(self):
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).exists())

    def test_cannot_review_when_applied(self):
        self._apply_with_status(APPLICATION_STATUS_APPLIED)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)

    def test_cannot_review_when_shortlisted(self):
        self._apply_with_status(APPLICATION_STATUS_SHORTLISTED)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)

    def test_cannot_review_when_interview(self):
        self._apply_with_status(APPLICATION_STATUS_INTERVIEW)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)

    def test_cannot_review_when_rejected(self):
        self._apply_with_status(APPLICATION_STATUS_REJECTED)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)

    def test_can_review_after_hired(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 200)

    def test_review_requires_rating_and_content_via_post(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.post(self._review_url(), {"content": "", "rating": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).exists())

    def test_review_requires_rating(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.post(self._review_url(), {"content": "Great place to work and learn new things."})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).exists())

    def test_review_requires_content(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.post(self._review_url(), {"rating": "5", "content": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).exists())

    def test_review_image_is_optional(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.post(
            self._review_url(), {"rating": "5", "content": "Great place to work and learn new things."}
        )
        self.assertEqual(response.status_code, 302)
        review = CompanyReview.objects.get(company=self.company, applicant=self.seeker)
        self.assertFalse(review.image)

    def test_review_image_upload_accepted(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.post(
            self._review_url(),
            {"rating": "4", "content": "Great place to work and learn new things.", "image": make_image()},
        )
        self.assertEqual(response.status_code, 302)
        review = CompanyReview.objects.get(company=self.company, applicant=self.seeker)
        self.assertTrue(review.image)

    def test_review_image_rejects_non_image_file(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        fake_exe = SimpleUploadedFile("bad.exe", b"MZfakecontent", content_type="application/octet-stream")
        response = self.client.post(
            self._review_url(),
            {"rating": "4", "content": "Great place to work and learn new things.", "image": fake_exe},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).exists())

    def test_review_appears_on_company_profile_after_submission(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        self.client.post(self._review_url(), {"rating": "5", "content": "Satisfied with the work environment."})
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "reviews"})
        self.assertContains(response, "Satisfied with the work environment.")

    def test_duplicate_review_prevented(self):
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        self.client.post(self._review_url(), {"rating": "5", "content": "Satisfied with the work environment."})
        self.assertEqual(CompanyReview.objects.filter(company=self.company, applicant=self.seeker).count(), 1)

        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 302)

        with self.assertRaises(Exception):
            CompanyReview.objects.create(
                company=self.company, applicant=self.seeker,
                application=Application.objects.get(job=self.job, applicant=self.seeker),
                rating=3, content="Trying to spam another review.",
            )

    def test_review_stores_correct_company_applicant_application_relationship(self):
        application = self._apply_with_status(APPLICATION_STATUS_HIRED)
        self.client.post(self._review_url(), {"rating": "5", "content": "Satisfied with the work environment."})
        review = CompanyReview.objects.get(company=self.company, applicant=self.seeker)
        self.assertEqual(review.company, self.company)
        self.assertEqual(review.applicant, self.seeker)
        self.assertEqual(review.application, application)

    def test_review_applicant_cannot_be_spoofed(self):
        """Server always sets applicant=request.user regardless of any submitted field."""
        self._apply_with_status(APPLICATION_STATUS_HIRED)
        other_user = User.objects.create_user(username="victim", password="pass12345")
        self.client.post(
            self._review_url(),
            {"rating": "5", "content": "Satisfied with the work environment.", "applicant": other_user.pk},
        )
        review = CompanyReview.objects.get(company=self.company)
        self.assertEqual(review.applicant, self.seeker)

    def test_employer_cannot_review_own_company(self):
        self.client.logout()
        self.client.login(username="hremp", password="pass12345")
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 403)

    def test_review_button_hidden_before_hiring_on_application_detail(self):
        application = self._apply_with_status(APPLICATION_STATUS_INTERVIEW)
        response = self.client.get(reverse("applications:detail", kwargs={"pk": application.pk}))
        self.assertNotContains(response, "Review Company")

    def test_review_button_shown_after_hiring_on_application_detail(self):
        application = self._apply_with_status(APPLICATION_STATUS_HIRED)
        response = self.client.get(reverse("applications:detail", kwargs={"pk": application.pk}))
        self.assertContains(response, "Review Company")


class CompanyReviewAggregationTests(TestCase):
    """spec sections 18/19: average/count/breakdown computed from real rows only."""

    def setUp(self):
        self.employer = User.objects.create_user(username="aggemp", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Aggregate Co")
        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Engineer",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )

    def _hired_review(self, username, rating):
        seeker = User.objects.create_user(username=username, password="pass12345")
        application = Application.objects.create(
            job=self.job, applicant=seeker, resume=make_resume(), status=APPLICATION_STATUS_HIRED,
        )
        return CompanyReview.objects.create(
            company=self.company, applicant=seeker, application=application,
            rating=rating, content="A perfectly reasonable review of this company.",
        )

    def test_no_reviews_yet(self):
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "reviews"})
        self.assertContains(response, "No reviews yet.")
        self.assertEqual(self.company.review_count(), 0)
        self.assertIsNone(self.company.review_average())

    def test_average_and_count_calculated_correctly(self):
        self._hired_review("r1", 5)
        self._hired_review("r2", 4)
        self._hired_review("r3", 3)
        self.assertEqual(self.company.review_count(), 3)
        self.assertAlmostEqual(self.company.review_average(), 4.0)

    def test_inactive_reviews_excluded_from_public_aggregates(self):
        review = self._hired_review("r4", 1)
        self._hired_review("r5", 5)
        review.is_active = False
        review.save(update_fields=["is_active"])
        self.assertEqual(self.company.review_count(), 1)
        self.assertAlmostEqual(self.company.review_average(), 5.0)

    def test_review_breakdown_counts_are_accurate(self):
        self._hired_review("r6", 5)
        self._hired_review("r7", 5)
        self._hired_review("r8", 1)
        breakdown = {row["star"]: row["count"] for row in self.company.review_breakdown()}
        self.assertEqual(breakdown[5], 2)
        self.assertEqual(breakdown[1], 1)
        self.assertEqual(breakdown[3], 0)


class CompanyReviewModerationTests(TestCase):
    """spec sections 20/21: HR can hide/show a review, never edit its content/rating."""

    def setUp(self):
        self.employer = User.objects.create_user(username="modemp", password="pass12345")
        self.employer.profile.role = ROLE_EMPLOYER
        self.employer.profile.save()
        self.company = Company.objects.create(owner=self.employer, name="Moderated Co")

        self.other_employer = User.objects.create_user(username="modemp2", password="pass12345")
        self.other_employer.profile.role = ROLE_EMPLOYER
        self.other_employer.profile.save()
        Company.objects.create(owner=self.other_employer, name="Other Moderated Co")

        self.job = Job.objects.create(
            employer=self.employer, company=self.company, title="Engineer",
            location="Remote", description="...", status=JOB_STATUS_PUBLISHED,
        )
        seeker = User.objects.create_user(username="modstudent", password="pass12345")
        application = Application.objects.create(
            job=self.job, applicant=seeker, resume=make_resume(), status=APPLICATION_STATUS_HIRED,
        )
        self.review = CompanyReview.objects.create(
            company=self.company, applicant=seeker, application=application,
            rating=5, content="Original student review text.",
        )

    def test_hr_can_hide_review_without_changing_content(self):
        self.client.login(username="modemp", password="pass12345")
        response = self.client.post(reverse("companies:review_toggle", kwargs={"pk": self.review.pk}))
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_active)
        self.assertEqual(self.review.content, "Original student review text.")
        self.assertEqual(self.review.rating, 5)

    def test_hidden_review_not_shown_publicly(self):
        self.review.is_active = False
        self.review.save(update_fields=["is_active"])
        response = self.client.get(reverse("companies:detail", kwargs={"slug": self.company.slug}), {"tab": "reviews"})
        self.assertNotContains(response, "Original student review text.")

    def test_other_employer_cannot_moderate_review(self):
        self.client.login(username="modemp2", password="pass12345")
        response = self.client.post(reverse("companies:review_toggle", kwargs={"pk": self.review.pk}))
        self.assertEqual(response.status_code, 403)

    def test_hr_sees_review_on_management_page(self):
        self.client.login(username="modemp", password="pass12345")
        response = self.client.get(reverse("companies:manage"))
        self.assertContains(response, "Original student review text.")

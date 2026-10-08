import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER
from resumes.models import ATSIssue, Resume, ResumeJobMatch, ResumeScan
from services.job_match_service import match_resume_to_job
from services.resume_analysis_service import analyze
from services.resume_parser_service import extract
from services.resume_service import ensure_parsed, run_job_match, run_resume_scan

User = get_user_model()

SAMPLE_RESUME_TEXT = """Arun Kumar
arun.kumar@example.com | +91 9876543210
Bengaluru, Karnataka
linkedin.com/in/arunkumar | github.com/arunkumar

SUMMARY
Fresher software developer with strong Python and Django skills.

SKILLS
Python, Django, REST API, MySQL, Git, JavaScript

EDUCATION
B.Tech Computer Science, ABC College, 2024, 8.2 CGPA

PROJECTS
Developed a Django REST Framework based job portal with MySQL backend serving 200+ users.

INTERNSHIPS
Software Intern at XYZ Pvt Ltd - built Python automation scripts.

CERTIFICATIONS
Python for Everybody - Coursera

ACHIEVEMENTS
Winner of college hackathon 2023.

LANGUAGES
English, Hindi, Kannada
"""


def _build_pdf_bytes(text=SAMPLE_RESUME_TEXT):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def _build_docx_bytes(text=SAMPLE_RESUME_TEXT):
    import docx

    document = docx.Document()
    for line in text.split("\n"):
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf_upload(name="resume.pdf"):
    return SimpleUploadedFile(name, _build_pdf_bytes(), content_type="application/pdf")


def make_docx_upload(name="resume.docx"):
    return SimpleUploadedFile(
        name, _build_docx_bytes(), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


class ResumeParserTests(TestCase):
    """Real PDF/DOCX parsing - text extraction, contact/name/skills/section detection."""

    def test_parses_pdf_contact_and_skills(self):
        file_obj = io.BytesIO(_build_pdf_bytes())
        file_obj.name = "resume.pdf"
        result = extract(file_obj)
        self.assertNotIn("error", result)
        self.assertEqual(result["contact"]["email"], "arun.kumar@example.com")
        self.assertIn("+91", result["contact"]["phone"])
        self.assertIn("linkedin.com/in/arunkumar", result["contact"]["linkedin"])
        self.assertIn("Python", result["skills"])
        self.assertIn("Django", result["skills"])
        self.assertEqual(result["name"], "Arun Kumar")

    def test_parses_docx_sections(self):
        file_obj = io.BytesIO(_build_docx_bytes())
        file_obj.name = "resume.docx"
        result = extract(file_obj)
        self.assertNotIn("error", result)
        self.assertTrue(result["sections"]["skills"])
        self.assertTrue(result["sections"]["education"])
        self.assertTrue(result["sections"]["projects"])
        self.assertTrue(result["sections"]["internships"])

    def test_unparseable_file_returns_error_not_exception(self):
        garbage = io.BytesIO(b"not a real pdf or docx")
        garbage.name = "resume.pdf"
        result = extract(garbage)
        self.assertIn("error", result)

    def test_unsupported_extension_returns_error(self):
        file_obj = io.BytesIO(b"hello")
        file_obj.name = "resume.txt"
        result = extract(file_obj)
        self.assertIn("error", result)


class ResumeAnalysisTests(TestCase):
    """The ATS engine - real, deterministic scoring from parsed content."""

    def setUp(self):
        file_obj = io.BytesIO(_build_pdf_bytes())
        file_obj.name = "resume.pdf"
        self.parsed = extract(file_obj)

    def test_score_is_deterministic_not_random(self):
        result1 = analyze(self.parsed)
        result2 = analyze(self.parsed)
        self.assertEqual(result1["score"], result2["score"])
        self.assertEqual(result1["score_breakdown"], result2["score_breakdown"])

    def test_score_breakdown_has_expected_components(self):
        result = analyze(self.parsed)
        breakdown = result["score_breakdown"]
        for key in ("ats_compatibility", "content_quality", "skills_coverage", "impact", "formatting", "student_readiness"):
            self.assertIn(key, breakdown)
            self.assertGreaterEqual(breakdown[key], 0)
            self.assertLessEqual(breakdown[key], 100)

    def test_fresher_with_no_experience_section_not_penalized_as_missing(self):
        result = analyze(self.parsed)
        # This sample resume has Projects + Internships but no "Experience"
        # section - it must be reported as not_applicable, never "missing".
        self.assertEqual(result["sections_report"]["experience"], "not_applicable")

    def test_weak_bullet_produces_high_priority_content_issue(self):
        result = analyze(self.parsed)
        content_issues = [i for i in result["issues"] if i["category"] == "content"]
        self.assertTrue(any(i["priority"] == "high" for i in content_issues))

    def test_parse_error_yields_zero_score_not_exception(self):
        result = analyze({"error": "could not read file"})
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["issues"][0]["category"], "document")


SACHIN_RESUME_TEXT = """SACHIN A R
Python Developer | Generative AI Enthusiast

Email: idpsachin@gmail.com
Phone: +91-93443-58554
Linkedin: linkedin.com/in/sachinar
Github: github.com/Sachin052005
Location: Chennai, India

PROFESIONAL SUMMARY

Python Developer with a strong foundation in Python and full-stack web development using Django. Gained hands-on experience through internships and real-world web application development. Completed a Generative AI course covering LLMs, Prompt Engineering, LangChain, and RAG. Seeking opportunities as a Software and AI Developer.

EDUCATION

Bachelor of Technology in Computer Science And Business Systems
K.S. Rangasamy College of Technology, Namakkal
Graduated: 2026
CGPA: 8.2/10.0

SKILLS

Programming: Python
Web Development: HTML, CSS, JavaScript, Django
Databases: SQL (MySQL)

EXPERIENCE

Uzhavar Choice | Freelance Web Developer | 2026

Web Development Intern | Ether Services, Coimbatore | Jul 2024 - Sep 2024

CERTIFICATIONS

NPTEL
Cloud Computing - Elite + Silver - Top 2%

PROJECTS

Text-Based Agriculture Advisor Chatbot

Voice-Based AI Concept Assistant
"""


class ResumeAccuracyRegressionTests(TestCase):
    """Regression test for a real reported ATS accuracy bug: a resume with
    (1) a misspelled "PROFESIONAL SUMMARY" heading, (2) a phone number in
    "+91-93443-58554" format (a hyphenated 5+5 split, not the 3-3-4 split
    the old phone regex assumed), and (3) an internship listed as a plain
    entry inside "EXPERIENCE" with no dedicated "Internships" heading - was
    wrongly reporting Summary Missing, Phone Not Detected, and Internships
    Missing even though all three are genuinely present."""

    def setUp(self):
        file_obj = io.BytesIO(_build_pdf_bytes(SACHIN_RESUME_TEXT))
        file_obj.name = "resume.pdf"
        self.parsed = extract(file_obj)

    def test_phone_detected_with_hyphenated_five_five_format(self):
        self.assertEqual(self.parsed["contact"]["phone"], "+91-93443-58554")

    def test_misspelled_summary_heading_still_detected(self):
        result = analyze(self.parsed)
        self.assertEqual(result["sections_report"]["summary"], "detected")

    def test_misspelled_summary_heading_flagged_not_hidden(self):
        result = analyze(self.parsed)
        spelling_issues = [i for i in result["issues"] if i["category"] == "spelling"]
        self.assertTrue(any("PROFESIONAL SUMMARY" in i["message"] for i in spelling_issues))
        self.assertTrue(any("PROFESSIONAL SUMMARY" in i.get("suggestion", "") for i in spelling_issues))

    def test_internship_inside_experience_section_detected(self):
        result = analyze(self.parsed)
        self.assertEqual(result["sections_report"]["internships"], "detected")
        # Experience itself must still contain the freelance entry - the
        # internship line is classified, not deleted/moved out of Experience.
        self.assertIn("Freelance Web Developer", self.parsed["sections"]["experience"])

    def test_missing_languages_and_achievements_reported_accurately(self):
        result = analyze(self.parsed)
        self.assertEqual(result["sections_report"]["languages"], "missing")
        self.assertEqual(result["sections_report"]["achievements"], "missing")

    def test_recommendations_are_not_empty_when_real_issues_exist(self):
        result = analyze(self.parsed)
        self.assertTrue(result["recommendations"])

    def test_bare_year_is_not_counted_as_a_quantified_achievement(self):
        # "2026", "2024" etc. must not inflate Impact - only a real
        # magnitude marker (%, $, k/m, x, +) counts.
        from services.resume_analysis_service import _QUANTIFIED_RE

        self.assertFalse(_QUANTIFIED_RE.search("Graduated: 2026"))
        self.assertTrue(_QUANTIFIED_RE.search("Improved performance by 30%"))
        self.assertTrue(_QUANTIFIED_RE.search("Served 200+ users"))


class JobMatchServiceTests(TestCase):
    def _job(self, **overrides):
        from jobs.models import Job

        defaults = dict(
            title="Python Developer", description="Django REST API MySQL role",
            skills="Python, Django, REST API, MySQL", preferred_skills="Docker, AWS",
            experience_min=0, experience_max=2, education_required="undergraduate",
            location="Bengaluru", work_mode="",
        )
        defaults.update(overrides)
        return Job(**defaults)

    def test_matching_resume_scores_higher_than_mismatched_one(self):
        job = self._job()
        good_match = match_resume_to_job(
            resume_text=SAMPLE_RESUME_TEXT, candidate_skills=["Python", "Django", "REST API", "MySQL"],
            candidate_experience_years=0, candidate_education_text="B.Tech Computer Science",
            candidate_location="Bengaluru", candidate_title="Software Developer",
            projects_text="Django REST Framework job portal", job=job,
        )
        bad_match = match_resume_to_job(
            resume_text="Civil engineering AutoCAD structural design",
            candidate_skills=["AutoCAD", "Civil Engineering"],
            candidate_experience_years=0, candidate_education_text="", candidate_location="",
            candidate_title="Civil Engineer", projects_text="", job=job,
        )
        self.assertGreater(good_match["compatibility_score"], bad_match["compatibility_score"])

    def test_missing_required_skills_reported_separately_from_preferred(self):
        job = self._job(skills="Python, AWS", preferred_skills="Docker")
        result = match_resume_to_job(
            resume_text="Python developer", candidate_skills=["Python"],
            candidate_experience_years=1, candidate_education_text="", candidate_location="",
            candidate_title="", projects_text="", job=job,
        )
        self.assertIn("AWS", result["missing_skills"])
        self.assertIn("Docker", result["analysis"]["missing_preferred_skills"])

    def test_no_required_skills_never_fabricates_a_match(self):
        job = self._job(skills="", preferred_skills="")
        result = match_resume_to_job(
            resume_text="anything", candidate_skills=[], candidate_experience_years=0,
            candidate_education_text="", candidate_location="", candidate_title="", projects_text="", job=job,
        )
        self.assertEqual(result["missing_skills"], [])

    def test_freeform_jd_matches_without_a_job_instance(self):
        """spec section 43: paste/upload JD sourcing shares the same engine
        as matching against a real Job - no job row required."""
        result = match_resume_to_job(
            resume_text="Experienced Python Django developer with REST API and MySQL background.",
            candidate_skills=["Python", "Django", "REST API"],
            candidate_experience_years=1, candidate_education_text="", candidate_location="",
            candidate_title="Python Developer", projects_text="",
            jd_title="Backend Engineer", jd_description="Looking for Python Django MySQL AWS developer.",
            jd_required_skills=["Python", "Django", "MySQL", "AWS"],
        )
        self.assertIn("AWS", result["missing_skills"])
        self.assertIn("Python", result["matched_skills"])
        self.assertEqual(result["analysis"]["jd_title"], "Backend Engineer")
        # No reliable required/preferred split from freeform text - reported
        # as n/a (None), never guessed.
        self.assertIsNone(result["analysis"]["preferred_skills_percent"])


class ResumeUploadAndVersioningTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="resumestudent", password="pass12345")
        self.student.profile.role = ROLE_JOB_SEEKER
        self.student.profile.save()
        self.client.login(username="resumestudent", password="pass12345")

    def test_upload_pdf_and_auto_scan(self):
        response = self.client.post(
            reverse("resumes:upload"), {"title": "Python Resume", "file": make_pdf_upload()}
        )
        self.assertEqual(response.status_code, 302)
        resume = Resume.objects.get(student=self.student)
        self.assertEqual(resume.parse_status, "parsed")
        self.assertTrue(resume.scans.exists())
        self.assertTrue(resume.is_primary, "first resume uploaded should become primary")

    def test_upload_docx(self):
        response = self.client.post(
            reverse("resumes:upload"), {"title": "DOCX Resume", "file": make_docx_upload()}
        )
        self.assertEqual(response.status_code, 302)
        resume = Resume.objects.get(student=self.student)
        self.assertEqual(resume.parse_status, "parsed")

    def test_upload_rejects_invalid_extension(self):
        bad_file = SimpleUploadedFile("resume.exe", b"not a resume", content_type="application/octet-stream")
        response = self.client.post(reverse("resumes:upload"), {"title": "Bad", "file": bad_file})
        self.assertEqual(response.status_code, 200)  # re-renders form with errors
        self.assertFalse(Resume.objects.filter(student=self.student).exists())

    def test_upload_rejects_empty_file(self):
        empty_file = SimpleUploadedFile("resume.pdf", b"", content_type="application/pdf")
        response = self.client.post(reverse("resumes:upload"), {"title": "Empty", "file": empty_file})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(student=self.student).exists())

    def test_upload_rejects_corrupted_pdf(self):
        fake_pdf = SimpleUploadedFile("resume.pdf", b"this is not really a pdf file", content_type="application/pdf")
        response = self.client.post(reverse("resumes:upload"), {"title": "Fake", "file": fake_pdf})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(student=self.student).exists())

    def test_rename_duplicate_set_primary_delete(self):
        resume = Resume.objects.create(student=self.student, title="Original", file=make_pdf_upload())

        response = self.client.post(reverse("resumes:rename", kwargs={"pk": resume.pk}), {"title": "Renamed"})
        self.assertEqual(response.status_code, 302)
        resume.refresh_from_db()
        self.assertEqual(resume.title, "Renamed")

        response = self.client.post(reverse("resumes:duplicate", kwargs={"pk": resume.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Resume.objects.filter(student=self.student).count(), 2)

        duplicate = Resume.objects.exclude(pk=resume.pk).get(student=self.student)
        response = self.client.post(reverse("resumes:set_primary", kwargs={"pk": duplicate.pk}))
        self.assertEqual(response.status_code, 302)
        duplicate.refresh_from_db()
        resume.refresh_from_db()
        self.assertTrue(duplicate.is_primary)
        self.assertFalse(resume.is_primary)

        response = self.client.post(reverse("resumes:delete", kwargs={"pk": resume.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Resume.objects.filter(pk=resume.pk).exists())

    def test_rescan_preserves_history_and_creates_new_scan(self):
        resume = Resume.objects.create(student=self.student, title="Rescan Test", file=make_pdf_upload())
        first_scan = run_resume_scan(resume)
        second_scan = run_resume_scan(resume)
        self.assertEqual(resume.scans.count(), 2)
        self.assertTrue(ResumeScan.objects.filter(pk=first_scan.pk).exists(), "old scan must not be deleted/overwritten")
        self.assertTrue(ResumeScan.objects.filter(pk=second_scan.pk).exists())

    def test_unchanged_resume_reuses_cached_parse(self):
        resume = Resume.objects.create(student=self.student, title="Cache Test", file=make_pdf_upload())
        ensure_parsed(resume)
        self.assertFalse(resume.needs_reparse())

    def test_run_job_match_creates_resume_job_match_row(self):
        from core.constants import JOB_STATUS_PUBLISHED
        from jobs.models import Job

        employer = User.objects.create_user(username="jm_employer", password="pass12345")
        employer.profile.role = ROLE_EMPLOYER
        employer.profile.save()
        from companies.models import Company

        company = Company.objects.create(owner=employer, name="JM Test Co")
        job = Job.objects.create(
            employer=employer, company=company, title="Python Developer",
            location="Bengaluru", description="Django role", skills="Python, Django",
            status=JOB_STATUS_PUBLISHED,
        )
        resume = Resume.objects.create(student=self.student, title="Match Test", file=make_pdf_upload())
        match = run_job_match(resume, job)
        self.assertIsInstance(match, ResumeJobMatch)
        self.assertGreater(match.compatibility_score, 0)

    def test_run_job_match_with_pasted_jd_text(self):
        resume = Resume.objects.create(student=self.student, title="Pasted JD Test", file=make_pdf_upload())
        match = run_job_match(resume, jd_text="Python Django MySQL developer needed.", jd_title="Pasted Job Description")
        self.assertIsInstance(match, ResumeJobMatch)
        self.assertIsNone(match.job)
        self.assertEqual(match.job_description_text, "Python Django MySQL developer needed.")

    def test_job_match_view_with_pasted_text(self):
        resume = Resume.objects.create(student=self.student, title="View Paste Test", file=make_pdf_upload())
        response = self.client.post(
            reverse("resumes:job_match", kwargs={"pk": resume.pk}),
            {"pasted_text": "Python Django MySQL developer needed for a growing team."},
        )
        self.assertEqual(response.status_code, 302)
        match = ResumeJobMatch.objects.get(resume=resume)
        self.assertIsNone(match.job)
        self.assertTrue(match.job_description_text)

    def test_job_match_view_with_uploaded_jd_file(self):
        resume = Resume.objects.create(student=self.student, title="View Upload JD Test", file=make_pdf_upload())
        jd_file = SimpleUploadedFile("jd.pdf", _build_pdf_bytes("Python Django MySQL developer needed."), content_type="application/pdf")
        response = self.client.post(
            reverse("resumes:job_match", kwargs={"pk": resume.pk}), {"jd_file": jd_file},
        )
        self.assertEqual(response.status_code, 302)
        match = ResumeJobMatch.objects.get(resume=resume)
        self.assertIsNone(match.job)
        self.assertIn("Python", match.job_description_text)

    def test_job_match_view_rejects_no_source_selected(self):
        resume = Resume.objects.create(student=self.student, title="No Source Test", file=make_pdf_upload())
        response = self.client.post(reverse("resumes:job_match", kwargs={"pk": resume.pk}), {})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ResumeJobMatch.objects.filter(resume=resume).exists())

    def test_job_match_view_rejects_multiple_sources_selected(self):
        from core.constants import JOB_STATUS_PUBLISHED
        from jobs.models import Job
        from companies.models import Company

        employer = User.objects.create_user(username="jm_multi_employer", password="pass12345")
        employer.profile.role = ROLE_EMPLOYER
        employer.profile.save()
        company = Company.objects.create(owner=employer, name="Multi Source Co")
        job = Job.objects.create(
            employer=employer, company=company, title="Python Developer",
            location="Bengaluru", description="Django role", skills="Python, Django",
            status=JOB_STATUS_PUBLISHED,
        )
        resume = Resume.objects.create(student=self.student, title="Multi Source Test", file=make_pdf_upload())
        response = self.client.post(
            reverse("resumes:job_match", kwargs={"pk": resume.pk}),
            {"job": job.pk, "pasted_text": "Also a pasted description."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ResumeJobMatch.objects.filter(resume=resume).exists())

    def test_scan_creates_ats_issue_rows_with_positions_when_anchored(self):
        resume = Resume.objects.create(student=self.student, title="Issue Test", file=make_pdf_upload())
        run_resume_scan(resume)
        issues = ATSIssue.objects.filter(resume=resume)
        self.assertTrue(issues.exists())
        anchored = issues.exclude(text="")
        for issue in anchored:
            self.assertIsNotNone(issue.start_position)
            self.assertEqual(resume.parsed_text[issue.start_position:issue.end_position], issue.text)


class ResumeSecurityTests(TestCase):
    """IDOR protection: a student can never reach another student's resume/scan."""

    def setUp(self):
        self.owner = User.objects.create_user(username="resumeowner", password="pass12345")
        self.owner.profile.role = ROLE_JOB_SEEKER
        self.owner.profile.save()
        self.other = User.objects.create_user(username="resumeother", password="pass12345")
        self.other.profile.role = ROLE_JOB_SEEKER
        self.other.profile.save()
        self.resume = Resume.objects.create(student=self.owner, title="Private Resume", file=make_pdf_upload())

    def test_other_student_cannot_view_detail(self):
        self.client.login(username="resumeother", password="pass12345")
        response = self.client.get(reverse("resumes:detail", kwargs={"pk": self.resume.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_student_cannot_download(self):
        self.client.login(username="resumeother", password="pass12345")
        response = self.client.get(reverse("resumes:download", kwargs={"pk": self.resume.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_student_cannot_delete(self):
        self.client.login(username="resumeother", password="pass12345")
        response = self.client.post(reverse("resumes:delete", kwargs={"pk": self.resume.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Resume.objects.filter(pk=self.resume.pk).exists())

    def test_owner_can_view_own_resume(self):
        self.client.login(username="resumeowner", password="pass12345")
        response = self.client.get(reverse("resumes:detail", kwargs={"pk": self.resume.pk}))
        self.assertEqual(response.status_code, 200)

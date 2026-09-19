import io
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from services import ats_service


def make_pdf_bytes(text):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx_bytes(paragraphs):
    import docx

    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class FakeFieldFile:
    """Minimal stand-in for a Django FieldFile, backed by in-memory bytes."""

    def __init__(self, name, data):
        self.name = name
        self._data = data

    def open(self, mode="rb"):
        return self

    def read(self):
        return self._data

    def close(self):
        pass

    def __bool__(self):
        return bool(self.name)


class NormalizeSkillsTests(SimpleTestCase):
    def test_aliases_are_canonicalized(self):
        result = ats_service.normalize_skills(["JS", "reactjs", "postgres", "ml"])
        self.assertEqual(result, ["JavaScript", "React", "PostgreSQL", "Machine Learning"])

    def test_unrelated_terms_are_left_alone(self):
        result = ats_service.normalize_skills(["Photoshop"])
        self.assertEqual(result, ["Photoshop"])

    def test_deduplicates_case_insensitively(self):
        result = ats_service.normalize_skills(["Python", "python", "PYTHON"])
        self.assertEqual(result, ["Python"])


class CompareSkillsTests(SimpleTestCase):
    def test_full_match(self):
        result = ats_service.compare_skills(["Python", "Django", "MySQL"], ["python", "django"])
        self.assertEqual(result["percent"], 100)
        self.assertEqual(result["missing"], [])

    def test_partial_match_reports_missing(self):
        result = ats_service.compare_skills(["Python"], ["Python", "Docker", "AWS"])
        self.assertEqual(result["percent"], 33)
        self.assertIn("Docker", result["missing"])
        self.assertIn("AWS", result["missing"])

    def test_no_job_skills_is_full_match(self):
        result = ats_service.compare_skills(["Python"], [])
        self.assertEqual(result["percent"], 100)


class ExtractResumeTextTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_pdf_extraction(self):
        data = make_pdf_bytes("Python Django MySQL Engineer with 3 years experience.")
        text, error = ats_service.extract_resume_text(FakeFieldFile("resumes/sample.pdf", data))
        self.assertEqual(error, "")
        self.assertIn("Python", text)

    def test_docx_extraction(self):
        data = make_docx_bytes(["Skills: Python, Django", "Education: B.Tech Computer Science"])
        text, error = ats_service.extract_resume_text(FakeFieldFile("resumes/sample.docx", data))
        self.assertEqual(error, "")
        self.assertIn("Python", text)
        self.assertIn("Education", text)

    def test_txt_extraction(self):
        text, error = ats_service.extract_resume_text(FakeFieldFile("resumes/sample.txt", b"Python developer"))
        self.assertEqual(error, "")
        self.assertIn("Python", text)

    def test_unsupported_extension_fails_gracefully(self):
        text, error = ats_service.extract_resume_text(FakeFieldFile("resumes/sample.doc", b"binary junk"))
        self.assertEqual(text, "")
        self.assertTrue(error)

    def test_no_file_fails_gracefully(self):
        text, error = ats_service.extract_resume_text(None)
        self.assertEqual(text, "")
        self.assertTrue(error)

    def test_corrupt_pdf_does_not_raise(self):
        text, error = ats_service.extract_resume_text(FakeFieldFile("resumes/broken.pdf", b"not a real pdf"))
        self.assertEqual(text, "")
        self.assertTrue(error)


class AnalyzeResumeTextTests(SimpleTestCase):
    def test_detects_standard_sections(self):
        text = (
            "John Doe\njohn@example.com\nProfessional Summary: Backend developer.\n"
            "Skills: Python, Django, MySQL\nEducation: B.Tech Computer Science\n"
            "Experience: 2 years at Acme\nProjects: job-portal\n"
            "linkedin.com/in/johndoe\ngithub.com/johndoe"
        )
        result = ats_service.analyze_resume_text(text)
        self.assertTrue(all(result["sections"].values()))
        self.assertEqual(result["readiness_percent"], 100)

    def test_empty_text_returns_zero_readiness(self):
        result = ats_service.analyze_resume_text("", extraction_error="")
        self.assertEqual(result["readiness_percent"], 0)
        self.assertTrue(result["issues"])


class AnalyzeJobMatchTests(TestCase):
    def _job(self):
        class FakeJob:
            title = "Python Developer"
            description = "Looking for a Python and Django developer with REST API experience."
            responsibilities = ""
            experience_min = 2

            def skills_list(self):
                return ["Python", "Django", "Docker"]

        return FakeJob()

    def _profile(self, skills="Python, Django", experience_years=2):
        class FakeProfile:
            def __init__(self, skills, experience_years):
                self.skills = skills
                self.experience_years = experience_years
                self.summary = "Backend developer."

            def skills_list(self):
                return [s.strip() for s in self.skills.split(",") if s.strip()]

        return FakeProfile(skills, experience_years)

    def test_weights_sum_to_overall_and_components_present(self):
        job = self._job()
        profile = self._profile()
        resume_text = "Python Django MySQL REST API. Education: B.Tech. Experience: 2 years."
        result = ats_service.analyze_job_match(profile, resume_text, job)

        self.assertEqual(sum(ats_service.ATS_WEIGHTS.values()), 100)
        self.assertIn("skills", result["components"])
        self.assertIn("experience", result["components"])
        self.assertIn("education", result["components"])
        self.assertIn("keyword", result["components"])
        self.assertIn("resume_completeness", result["components"])
        for component in result["components"].values():
            self.assertIn("reason", component)
            self.assertTrue(component["reason"])
        self.assertTrue(0 <= result["overall_percent"] <= 100)
        self.assertIn("Docker", result["missing_skills"])
        self.assertEqual(result["disclaimer"], ats_service.ATS_MATCH_DISCLAIMER)

    def test_never_claims_hiring_guarantee(self):
        result = ats_service.analyze_job_match(self._profile(), "Python Django", self._job())
        self.assertIn("informational", result["disclaimer"].lower())
        self.assertIn("not a guarantee", result["disclaimer"].lower())


class GithubAnalysisTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_invalid_url_returns_invalid_status(self):
        result = ats_service.analyze_github_profile("https://example.com/notgithub")
        self.assertEqual(result["status"], "invalid_url")

    def test_blank_url_returns_invalid_status(self):
        result = ats_service.analyze_github_profile("")
        self.assertEqual(result["status"], "invalid_url")

    @patch("services.ats_service.requests.get")
    def test_successful_fetch_detects_technologies(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "job-portal", "description": "Django REST job board", "language": "Python", "topics": ["docker"]},
            {"name": "notes-app", "description": "React notes app", "language": "JavaScript", "topics": []},
        ]
        result = ats_service.analyze_github_profile("https://github.com/exampleuser")
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["repository_count"], 2)
        self.assertIn("Python", result["detected_technologies"])
        self.assertIn("JavaScript", result["detected_technologies"])

    @patch("services.ats_service.requests.get")
    def test_404_returns_not_found(self, mock_get):
        mock_get.return_value.status_code = 404
        result = ats_service.analyze_github_profile("https://github.com/doesnotexist")
        self.assertEqual(result["status"], "not_found")

    @patch("services.ats_service.requests.get")
    def test_network_failure_returns_unavailable_and_never_raises(self, mock_get):
        import requests

        mock_get.side_effect = requests.Timeout("timed out")
        result = ats_service.analyze_github_profile("https://github.com/exampleuser2")
        self.assertEqual(result["status"], "unavailable")

    @patch("services.ats_service.requests.get")
    def test_rate_limit_returns_rate_limited_status(self, mock_get):
        mock_get.return_value.status_code = 403
        result = ats_service.analyze_github_profile("https://github.com/exampleuser3")
        self.assertEqual(result["status"], "rate_limited")


class LinkedInAnalysisTests(SimpleTestCase):
    def test_valid_linkedin_url(self):
        result = ats_service.analyze_linkedin_url("https://www.linkedin.com/in/example")
        self.assertEqual(result["status"], "manual_review")

    def test_invalid_host_rejected(self):
        result = ats_service.analyze_linkedin_url("https://example.com/in/someone")
        self.assertEqual(result["status"], "invalid_url")

    def test_blank_url(self):
        result = ats_service.analyze_linkedin_url("")
        self.assertEqual(result["status"], "not_provided")

    def test_never_scrapes_or_raises(self):
        # No network call is made for LinkedIn under any circumstance.
        with patch("services.ats_service.requests.get") as mock_get:
            ats_service.analyze_linkedin_url("https://www.linkedin.com/in/example")
            mock_get.assert_not_called()

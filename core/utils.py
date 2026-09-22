import uuid
from pathlib import Path

# Maintainable alias table: raw term (lowercase) -> canonical display name.
# Only genuinely equivalent terms are mapped here - never loosely related ones.
# Moved here from the removed services/ats_service.py - this normalization is
# used by CandidateSkill/Profile (accounts) independent of any ATS feature.
SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "vuejs": "Vue.js",
    "vue": "Vue.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "node.js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "mysql": "MySQL",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "restful api": "REST API",
    "restful apis": "REST API",
    "rest api": "REST API",
    "rest apis": "REST API",
    "drf": "Django REST Framework",
    "django rest framework": "Django REST Framework",
    "django-rest-framework": "Django REST Framework",
    "html5": "HTML",
    "html": "HTML",
    "css3": "CSS",
    "css": "CSS",
    "py": "Python",
    "python3": "Python",
    "python": "Python",
    "django": "Django",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "azure": "Azure",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "redis": "Redis",
    "git": "Git",
    "github": "GitHub",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
}


def normalize_skill(raw):
    key = raw.strip().lower()
    return SKILL_ALIASES.get(key, raw.strip())


class UploadTo:
    """Deconstructible upload_to callable so migrations can serialize it by subfolder name."""

    def __init__(self, subfolder):
        self.subfolder = subfolder

    def __call__(self, instance, filename):
        ext = Path(filename).suffix.lower()
        return f"{self.subfolder}/{uuid.uuid4().hex}{ext}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and self.subfolder == other.subfolder

    def deconstruct(self):
        return ("core.utils.UploadTo", [self.subfolder], {})


def unique_upload_path(subfolder):
    return UploadTo(subfolder)

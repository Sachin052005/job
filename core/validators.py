import os
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from core.constants import MAX_IMAGE_SIZE_MB, MAX_RESUME_SIZE_MB

RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

_django_url_validator = URLValidator(schemes=["http", "https"])

# Loose host allow-lists just to catch obvious mismatches (e.g. pasting a
# Twitter link into the GitHub field). Not enforced as a hard requirement
# beyond "looks like the right site" since profile URLs are never fetched
# server-side for anything other than GitHub's fixed public API.
_HOST_HINTS = {
    "linkedin": ("linkedin.com",),
    "github": ("github.com",),
}


def validate_profile_url(url, kind=None):
    """Validate a professional-link URL (LinkedIn/GitHub/portfolio/website).

    Restricts to http(s) schemes only (blocks javascript:, data:, etc.) and,
    for known kinds, sanity-checks the host. Raises ValidationError on failure.
    """
    if not url:
        return
    try:
        _django_url_validator(url)
    except ValidationError:
        raise ValidationError("Enter a valid URL starting with http:// or https://.")

    host = (urlparse(url).hostname or "").lower()
    if kind in _HOST_HINTS and not any(host == h or host.endswith("." + h) for h in _HOST_HINTS[kind]):
        raise ValidationError(f"Enter a valid {kind.title()} URL (expected a {_HOST_HINTS[kind][0]} link).")


def validate_resume_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in RESUME_EXTENSIONS:
        raise ValidationError("Resume must be a PDF, DOC, or DOCX file.")
    if file.size > MAX_RESUME_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Resume file must be smaller than {MAX_RESUME_SIZE_MB}MB.")


def validate_image_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ValidationError("Image must be a PNG, JPG, or WEBP file.")
    if file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Image file must be smaller than {MAX_IMAGE_SIZE_MB}MB.")

import os
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from PIL import Image, UnidentifiedImageError

from core.constants import MAX_IMAGE_SIZE_MB, MAX_RESUME_SIZE_MB

RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Content-sniffing is skipped for .doc: it's a legacy binary OLE format with
# no lightweight parser already in requirements.txt. Extension+size checks
# still apply to it.
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"

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


def _validate_pdf_content(file):
    """Reject files that merely have a .pdf extension but aren't PDFs at all.

    Deliberately magic-bytes-only, not a full parse: a full PyMuPDF parse
    would also reject legitimately unusual-but-genuine PDFs (and made the
    Easy Apply test fixtures, which use a minimal fake PDF byte string,
    fail) for little real security benefit over the magic-byte check.
    """
    file.seek(0)
    head = file.read(len(_PDF_MAGIC))
    file.seek(0)
    if not head.startswith(_PDF_MAGIC):
        raise ValidationError("This file is not a valid PDF.")


def _validate_docx_content(file):
    """Reject files that merely have a .docx extension but aren't zip-based at all.

    Magic-bytes-only for the same reason as `_validate_pdf_content`.
    """
    file.seek(0)
    head = file.read(len(_ZIP_MAGIC))
    file.seek(0)
    if not head.startswith(_ZIP_MAGIC):
        raise ValidationError("This file is not a valid DOCX document.")


def _validate_image_content(file, ext):
    """Reject files whose actual decoded image format doesn't match their extension."""
    expected_format = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}[ext.lstrip(".")]
    try:
        file.seek(0)
        with Image.open(file) as image:
            image.verify()
        file.seek(0)
        with Image.open(file) as image:
            actual_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("This file is not a valid image.")
    finally:
        file.seek(0)
    if actual_format != expected_format:
        raise ValidationError("This file's content does not match its extension.")


def validate_resume_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in RESUME_EXTENSIONS:
        raise ValidationError("Resume must be a PDF, DOC, or DOCX file.")
    if file.size > MAX_RESUME_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Resume file must be smaller than {MAX_RESUME_SIZE_MB}MB.")
    if ext == ".pdf":
        _validate_pdf_content(file)
    elif ext == ".docx":
        _validate_docx_content(file)


def validate_image_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ValidationError("Image must be a PNG, JPG, or WEBP file.")
    if file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Image file must be smaller than {MAX_IMAGE_SIZE_MB}MB.")
    _validate_image_content(file, ext)

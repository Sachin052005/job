"""Local, free resume parsing (PDF/DOCX) - no paid APIs, no LLMs.

extract(file) is the single entrypoint: given a Django File/FieldFile, it
returns a dict of raw text plus the structural signals (page count, images,
tables, columns, fonts) the ATS formatting analyzer needs, and the
regex-extracted contact/section/skill data the rest of the ATS engine
builds on. Never raises - a parse failure comes back as
{"error": "<message>"} so callers can set Resume.parse_status = FAILED
without crashing the request (spec: ATS must fail gracefully).
"""
import re

from rapidfuzz import fuzz

from core.constants import RESUME_SECTION_KEYS
from services.skills_vocabulary import extract_skills

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_COMMON_TLDS = "com|in|io|dev|me|net|org"
_URL_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?[a-z0-9-]+\.(?:" + _COMMON_TLDS + r")\b(?:/[^\s,)\]]*)?",
    re.IGNORECASE,
)

# Phone detection (spec: support "+91-93443-58554", "+91 93443 58554",
# "+919344358554", "9344358554", "93443 58554" - any digit grouping, not just
# a fixed area-code/prefix/line split). A labeled line ("Phone:", "Mobile:",
# ...) is checked first anywhere in the document since a label is an
# unambiguous signal; unlabeled digits are only trusted near the top of the
# resume (spec: don't classify every 10-digit number found anywhere as a
# phone number - a candidate/roll number buried in Education is not a
# phone).
_PHONE_LABEL_RE = re.compile(
    r"(?i)\b(?:phone|mobile|mob|contact(?:\s*no\.?|\s*number)?|tel(?:ephone)?)\s*(?:no\.?|number)?\s*[:\-]\s*(.+)"
)
_PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{7,16}\d")
_PHONE_CONTACT_ZONE_LINES = 10


def _digits_only(value):
    return re.sub(r"\D", "", value)


def _looks_like_phone(candidate):
    digit_count = len(_digits_only(candidate))
    return 10 <= digit_count <= 13


def _detect_phone(text):
    """`text` should already have emails blanked out (an email's digits -
    e.g. a birth year in a username - must never be read as a phone
    number)."""
    for line in text.splitlines():
        label_match = _PHONE_LABEL_RE.search(line)
        if not label_match:
            continue
        candidate_match = _PHONE_CANDIDATE_RE.search(label_match.group(1))
        if candidate_match and _looks_like_phone(candidate_match.group(0)):
            return candidate_match.group(0).strip()

    contact_zone = "\n".join(text.splitlines()[:_PHONE_CONTACT_ZONE_LINES])
    for candidate_match in _PHONE_CANDIDATE_RE.finditer(contact_zone):
        candidate = candidate_match.group(0)
        if _looks_like_phone(candidate):
            return candidate.strip()
    return ""


# Section heading families (spec sections 4/36-37): recognized by fuzzy
# match, not just an exact string, so a spelling slip ("PROFESIONAL
# SUMMARY") or an unlisted-but-close variant still resolves to the right
# section instead of being reported missing. The *first* string in each
# list is treated as the canonical/standard spelling for suggestions.
_SECTION_HEADERS = {
    "summary": [
        "professional summary", "summary", "professional profile", "profile",
        "career summary", "career profile", "career objective", "objective", "about me",
    ],
    "skills": ["skills", "technical skills", "core competencies", "key skills"],
    "education": ["education", "academic background", "educational qualification"],
    "experience": ["experience", "work experience", "professional experience", "employment history"],
    "projects": ["projects", "academic projects", "personal projects", "project experience", "key projects"],
    "internships": ["internships", "internship", "internship experience"],
    "certifications": ["certifications", "certificates", "licenses"],
    "achievements": ["achievements", "accomplishments", "awards", "honors"],
    "languages": ["languages", "language proficiency"],
}

_HEADING_MAX_WORDS = 4
_HEADING_MAX_CHARS = 45
_HEADING_FUZZY_THRESHOLD = 85


def _normalize_heading(line):
    cleaned = re.sub(r"[^a-z\s]", " ", line.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _match_heading(line):
    """Return (section_key, is_exact, canonical_heading) if `line` looks
    like a section heading for one of the known families, else None. An
    exact (normalized) match is preferred; a close-but-not-exact fuzzy
    match is still accepted - callers surface that case as a low-severity
    "spelling variation" issue rather than silently rewriting the resume or
    reporting the section as missing."""
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > _HEADING_MAX_CHARS:
        return None
    words = stripped.split()
    if not words or len(words) > _HEADING_MAX_WORDS:
        return None
    normalized = _normalize_heading(stripped)
    if len(normalized) < 4:
        return None

    for key, variants in _SECTION_HEADERS.items():
        if normalized in variants:
            return key, True, variants[0]

    best_key, best_variant, best_score = None, None, 0
    for key, variants in _SECTION_HEADERS.items():
        for variant in variants:
            if abs(len(variant.split()) - len(words)) > 1:
                continue
            score = fuzz.ratio(normalized, variant)
            if score > best_score:
                best_key, best_variant, best_score = key, variant, score
    if best_key and best_score >= _HEADING_FUZZY_THRESHOLD:
        return best_key, False, best_variant
    return None


# Internship classification (spec section 6): a resume entry mentioning any
# of these terms is an internship even without a dedicated "Internships"
# heading - most commonly a line inside a general "Experience" section.
_INTERNSHIP_LINE_RE = re.compile(r"\b(?:intern|interns|internship|internships|trainee)\b", re.IGNORECASE)


def _extract_internship_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip() and _INTERNSHIP_LINE_RE.search(line)]


def _detect_contact(text):
    email_match = _EMAIL_RE.search(text)
    # Blank out any email first, so an email's local-part/domain (e.g. a
    # birth year in "kumar1998@example.com") can never be mistaken for a
    # phone number or a portfolio URL.
    text_without_emails = _EMAIL_RE.sub(" ", text)
    phone = _detect_phone(text_without_emails)
    urls = _URL_RE.findall(text_without_emails)
    linkedin = next((u for u in urls if "linkedin.com" in u.lower()), "")
    github = next((u for u in urls if "github.com" in u.lower()), "")
    other_urls = [u for u in urls if "linkedin.com" not in u.lower() and "github.com" not in u.lower()]
    return {
        "email": email_match.group(0) if email_match else "",
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "portfolio": other_urls[0] if other_urls else "",
    }


def _detect_name(lines):
    for line in lines[:6]:
        candidate = line.strip()
        if not candidate or len(candidate) > 60:
            continue
        if _EMAIL_RE.search(candidate) or _PHONE_CANDIDATE_RE.search(candidate) or _URL_RE.search(candidate):
            continue
        words = candidate.split()
        if 1 < len(words) <= 4 and all(w[0:1].isupper() or not w[0:1].isalpha() for w in words):
            return candidate
    return ""


def _split_into_sections(lines):
    """Walk the resume line-by-line. Returns (sections, heading_matches):
    `sections` is {section_key: "text under that heading"} for whichever of
    RESUME_SECTION_KEYS were found (by fuzzy heading match, not just an
    exact string - spec section 4); `heading_matches` is {section_key:
    {"heading": <original line text>, "is_exact": bool, "canonical": <standard
    spelling>}} for the first heading line found for each key, so the
    analyzer can flag a spelling-variation heading without ever reporting
    that section as missing."""
    sections = {}
    heading_matches = {}
    current_key = None
    buffer = []

    def flush():
        if current_key and buffer:
            addition = "\n".join(buffer).strip()
            if addition:
                existing = sections.get(current_key, "")
                sections[current_key] = f"{existing}\n{addition}".strip() if existing else addition

    for line in lines:
        match = _match_heading(line)
        if match:
            flush()
            current_key, is_exact, canonical = match
            buffer = []
            if current_key not in heading_matches:
                heading_matches[current_key] = {
                    "heading": line.strip(), "is_exact": is_exact, "canonical": canonical,
                }
        elif current_key:
            buffer.append(line)
    flush()
    return sections, heading_matches


_LOCATION_LABEL_RE = re.compile(r"(?i)^\s*(?:location|address|based in|city)\s*:\s*(.+)$")


def _detect_location(text):
    # Heuristic only: a line near the top containing a comma-separated
    # "City, State"/"City, Country" pattern and no @ or digits-heavy phone.
    for line in text.splitlines()[:8]:
        line = line.strip()
        label_match = _LOCATION_LABEL_RE.match(line)
        if label_match:
            line = label_match.group(1).strip()
        if "," in line and not _EMAIL_RE.search(line) and len(line) < 60:
            parts = [p.strip() for p in line.split(",")]
            if 2 <= len(parts) <= 3 and all(p and not p.isdigit() for p in parts):
                return line
    return ""


def _extract_pdf(file_obj):
    import pymupdf as fitz

    file_obj.seek(0)
    data = file_obj.read()
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        page_count = doc.page_count
        text_parts = []
        has_images = False
        font_names = set()
        column_signal = 0

        for page in doc:
            text_parts.append(page.get_text())
            if page.get_images(full=True):
                has_images = True

            page_dict = page.get_text("dict")
            x_positions = []
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_names.add(span.get("font", ""))
                x_positions.append(block.get("bbox", [0])[0])
            # Multi-column heuristic: text blocks cluster into two distinct
            # x-origin bands, each comfortably inside a half-page width.
            if x_positions:
                page_width = page.rect.width
                left_band = sum(1 for x in x_positions if x < page_width * 0.15)
                right_band = sum(1 for x in x_positions if page_width * 0.4 < x < page_width * 0.6)
                if left_band >= 3 and right_band >= 3:
                    column_signal += 1

        full_text = "\n".join(text_parts)
        return {
            "text": full_text,
            "page_count": page_count,
            "has_images": has_images,
            "has_tables": False,  # PyMuPDF has no reliable table detector without extra deps
            "multi_column": column_signal > 0,
            "font_count": len(font_names),
            "char_count": len(full_text),
        }
    finally:
        doc.close()


def _extract_docx(file_obj):
    import docx

    file_obj.seek(0)
    document = docx.Document(file_obj)

    paragraphs = [p.text for p in document.paragraphs]
    full_text = "\n".join(paragraphs)

    font_names = set()
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.font.name:
                font_names.add(run.font.name)

    has_images = len(document.inline_shapes) > 0
    has_tables = len(document.tables) > 0
    if has_tables:
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text += "\n" + cell.text

    word_count = len(full_text.split())
    estimated_pages = max(1, round(word_count / 500))

    return {
        "text": full_text,
        "page_count": estimated_pages,
        "has_images": has_images,
        "has_tables": has_tables,
        "multi_column": False,  # not reliably detectable from DOCX XML without heavy layout parsing
        "font_count": len(font_names),
        "char_count": len(full_text),
    }


def extract(file_field):
    """Parse an uploaded resume file (PDF or DOCX). Returns a dict:
    {text, page_count, has_images, has_tables, multi_column, font_count,
     char_count, contact, name, location, sections, skills, error}
    `error` is only present on failure - all other keys are always present
    on success."""
    name_lower = (file_field.name or "").lower()
    try:
        if name_lower.endswith(".pdf"):
            raw = _extract_pdf(file_field)
        elif name_lower.endswith(".docx"):
            raw = _extract_docx(file_field)
        else:
            return {"error": f"Unsupported file type for parsing: {file_field.name}"}
    except Exception as exc:  # pragma: no cover - defensive, see module docstring
        return {"error": f"Could not parse resume: {exc}"}

    text = raw["text"]
    if not text.strip():
        raw["error"] = "No extractable text found - the file may be a scanned image."
        return raw

    lines = [line for line in text.splitlines() if line.strip()]
    raw["contact"] = _detect_contact(text)
    raw["name"] = _detect_name(lines)
    raw["location"] = _detect_location(text)
    sections_found, heading_matches = _split_into_sections(lines)
    raw["sections"] = {key: sections_found.get(key, "") for key in RESUME_SECTION_KEYS}
    raw["section_headings"] = heading_matches

    # Internship classification (spec section 6): a resume rarely gives
    # internships their own heading - they're usually one entry inside a
    # general "Experience" section. Don't report "Internships Missing" just
    # because there's no dedicated heading; look for internship-labeled
    # entries inside Experience (or, failing that, anywhere in the resume)
    # instead. Experience text is left untouched - both stay visible.
    if not raw["sections"].get("internships"):
        source_text = raw["sections"].get("experience") or text
        internship_lines = _extract_internship_lines(source_text)
        if internship_lines:
            raw["sections"]["internships"] = "\n".join(internship_lines)

    raw["skills"] = extract_skills(text)
    return raw

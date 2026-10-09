"""TalentPanda's own local Resume Health / ATS Compatibility analysis -
deterministic, rule-based, no paid APIs or LLMs. Every score here is
computed from the actual parsed resume; nothing is hardcoded or random.

Entry point: analyze(parsed) -> {
    "score": int,                # overall Resume Health, 0-100
    "score_breakdown": {...},    # ATS Compatibility, Content Quality, Skills
                                  # Coverage, Impact, Formatting, Student Readiness
    "issues": [...],             # Fix Center feed: {priority, category, message}
    "recommendations": [...],    # actionable suggestions (strings)
    "sections_report": {...},    # per-section detected/missing/possibly_detected
}
`parsed` is the dict returned by services.resume_parser_service.extract().
"""
import re

from core.constants import ISSUE_PRIORITY_HIGH, ISSUE_PRIORITY_LOW, ISSUE_PRIORITY_MEDIUM

ACTION_VERBS = {
    "developed", "built", "designed", "implemented", "created", "led", "managed", "improved",
    "optimized", "reduced", "increased", "launched", "automated", "engineered", "architected",
    "deployed", "streamlined", "delivered", "coordinated", "analyzed", "resolved", "migrated",
    "refactored", "mentored", "trained", "presented", "negotiated", "achieved", "won", "drove",
    "spearheaded", "established", "integrated", "configured", "tested", "debugged", "wrote",
    "authored", "scaled", "collaborated", "researched", "generated", "processed", "handled",
    "supervised", "planned", "organized", "executed", "maintained", "supported", "documented",
}

FILLER_PHRASES = [
    "responsible for", "worked on", "helped with", "involved in", "in charge of",
    "duties included", "tasked with", "assisted with", "participated in", "was part of",
]

PERSONAL_PRONOUNS = {"i", "me", "my", "myself", "we", "our", "us"}

_PASSIVE_RE = re.compile(
    r"\b(was|were|is|are|been|being|be)\s+\w+ed\b", re.IGNORECASE
)
# A quantified result needs a unit/magnitude marker (%, $, k/m, x, or a "+"
# count) - a bare number on its own (a year, a page number, a CGPA digit) is
# not an achievement and must not inflate the Impact score.
_QUANTIFIED_RE = re.compile(
    r"\d+(\.\d+)?\s*%" r"|\$\s*\d" r"|\b\d+(?:[kKmM]|x)\b" r"|\b\d+\+",
    re.IGNORECASE,
)
_BULLET_LINE_RE = re.compile(r"^\s*[-*••]\s*(.+)$")


def _bullet_lines(text):
    """Lines that look like resume bullets - either explicitly marked (-, *, •)
    or short standalone lines under Experience/Projects/Internships sections."""
    bullets = []
    for raw_line in text.splitlines():
        match = _BULLET_LINE_RE.match(raw_line)
        if match:
            bullets.append(match.group(1).strip())
    return bullets


def _analyze_bullets(all_bullet_text_blocks):
    bullets = []
    for block in all_bullet_text_blocks:
        bullets.extend(_bullet_lines(block))
        # Fall back to treating each non-empty line as a bullet when the
        # section has no explicit markers (common in simple resumes).
        if not _bullet_lines(block):
            bullets.extend(line.strip() for line in block.splitlines() if line.strip())

    if not bullets:
        return {"count": 0, "with_action_verb": 0, "with_quantification": 0, "weak_examples": []}

    with_action_verb = 0
    with_quantification = 0
    weak_examples = []
    for bullet in bullets:
        words = bullet.split()
        if not words:
            continue
        first_word = re.sub(r"[^a-zA-Z]", "", words[0]).lower()
        has_verb = first_word in ACTION_VERBS
        has_quant = bool(_QUANTIFIED_RE.search(bullet))
        if has_verb:
            with_action_verb += 1
        if has_quant:
            with_quantification += 1
        if not has_verb and not has_quant and len(weak_examples) < 3:
            weak_examples.append(bullet[:160])

    return {
        "count": len(bullets),
        "with_action_verb": with_action_verb,
        "with_quantification": with_quantification,
        "weak_examples": weak_examples,
    }


def _content_quality(parsed, sections_report):
    text = parsed.get("text", "")
    section_texts = [v for v in parsed.get("sections", {}).values() if v]
    bullet_stats = _analyze_bullets(section_texts or [text])

    issues = []
    recommendations = []

    filler_hits = [phrase for phrase in FILLER_PHRASES if phrase in text.lower()]
    if filler_hits:
        issues.append({
            "priority": ISSUE_PRIORITY_MEDIUM, "category": "content",
            "message": f"Filler phrases detected ({', '.join(filler_hits[:3])}) - replace with a specific action verb.",
        })

    words = re.findall(r"[a-zA-Z']+", text.lower())
    pronoun_count = sum(1 for w in words if w in PERSONAL_PRONOUNS)
    if pronoun_count > 2:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "content",
            "message": "Personal pronouns (I, my, we) found - resume bullets read stronger without them.",
        })

    passive_hits = len(_PASSIVE_RE.findall(text))
    if passive_hits > 2:
        issues.append({
            "priority": ISSUE_PRIORITY_MEDIUM, "category": "content",
            "message": f"Passive voice detected in {passive_hits} place(s) - prefer active voice (\"Developed X\" rather than \"X was developed\").",
        })

    if bullet_stats["count"]:
        verb_ratio = bullet_stats["with_action_verb"] / bullet_stats["count"]
        quant_ratio = bullet_stats["with_quantification"] / bullet_stats["count"]
    else:
        verb_ratio = quant_ratio = 0.0

    if verb_ratio < 0.5:
        issues.append({
            "priority": ISSUE_PRIORITY_HIGH, "category": "content",
            "message": "Most bullet points don't start with a strong action verb (e.g. Developed, Led, Improved).",
        })
    if quant_ratio < 0.3:
        issues.append({
            "priority": ISSUE_PRIORITY_MEDIUM, "category": "content",
            "message": "Few bullet points include a measurable result (a number, percentage, or amount).",
        })
        recommendations.append(
            "Add a measurable outcome to your bullet points where genuinely true, "
            "e.g. \"Developed a Django REST API used by 200+ students\" rather than \"Worked on a project using Python.\""
        )

    for example in bullet_stats["weak_examples"]:
        # A position-anchored issue (spec: red-underline system) - `text`
        # is the exact quoted span resumes.services will locate inside
        # parsed_text to compute start_position/end_position for an
        # ATSIssue row, and to highlight in the resume preview.
        issues.append({
            "priority": ISSUE_PRIORITY_HIGH, "category": "content", "section": "experience",
            "message": "Weak action phrase or generic wording.",
            "text": example,
            "suggestion": "Describe what you actually built, implemented, improved, or achieved - using only facts already in your resume.",
        })

    # Content Quality score: weighted mix of action-verb usage, quantification,
    # and the absence of filler/pronoun/passive issues.
    penalty = min(30, len(filler_hits) * 6 + min(pronoun_count, 5) * 2 + min(passive_hits, 5) * 2)
    score = round(max(0, verb_ratio * 55 + quant_ratio * 45 - penalty))
    score = max(0, min(100, score))

    return {
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
        "bullet_stats": bullet_stats,
    }


def _formatting(parsed):
    issues = []
    score = 100

    if parsed.get("multi_column"):
        issues.append({
            "priority": ISSUE_PRIORITY_HIGH, "category": "formatting",
            "message": "Resume appears to use a multi-column layout, which can break text extraction in many ATS systems.",
        })
        score -= 30

    if parsed.get("has_tables"):
        issues.append({
            "priority": ISSUE_PRIORITY_MEDIUM, "category": "formatting",
            "message": "Resume contains tables - some ATS systems misread table content or skip it entirely.",
        })
        score -= 15

    if parsed.get("has_images"):
        issues.append({
            "priority": ISSUE_PRIORITY_MEDIUM, "category": "formatting",
            "message": "Resume contains images (e.g. a photo or icons) - ATS systems cannot read text inside images.",
        })
        score -= 10

    page_count = parsed.get("page_count", 1)
    if page_count > 2:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "formatting",
            "message": f"Resume is {page_count} pages - consider trimming to 1-2 pages unless you have 8+ years of experience.",
        })
        score -= 10

    char_count = parsed.get("char_count", 0)
    if page_count and char_count / max(page_count, 1) < 400:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "formatting",
            "message": "Pages contain relatively little text - large empty areas can look sparse to a recruiter.",
        })
        score -= 5

    font_count = parsed.get("font_count", 0)
    if font_count and font_count > 4:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "formatting",
            "message": f"{font_count} different fonts detected - keeping to 1-2 fonts looks more consistent.",
        })
        score -= 5

    return {"score": max(0, score), "issues": issues}


def _sections(parsed, has_professional_experience_elsewhere=False):
    """Fresher-safe section report (spec: don't mark a fresher resume
    incomplete for lacking professional experience). A section is
    "possibly_detected" when short/ambiguous text was captured under its
    heading, "missing" only for sections with no signal at all, and
    Experience is never counted against freshers who have Projects or
    Internships instead."""
    sections = parsed.get("sections", {})
    report = {}
    for key, content in sections.items():
        if content and len(content.strip()) >= 15:
            report[key] = "detected"
        elif content:
            report[key] = "possibly_detected"
        else:
            report[key] = "missing"

    has_experience_signal = report.get("experience") == "detected"
    has_alt_experience = report.get("projects") == "detected" or report.get("internships") == "detected"
    if report.get("experience") == "missing" and (has_alt_experience or has_professional_experience_elsewhere):
        report["experience"] = "not_applicable"

    return report


def _skills_coverage(parsed, profile_skills=None):
    detected = parsed.get("skills", [])
    if profile_skills:
        overlap = len(set(s.lower() for s in detected) & set(s.lower() for s in profile_skills))
        base = round((overlap / len(profile_skills)) * 100) if profile_skills else 0
    else:
        base = min(100, len(detected) * 10)
    return base


def _student_readiness(parsed, sections_report):
    """Fresher Readiness (spec parts 18/27): rewards the things a fresher can
    actually have - education, projects, internships, skills, certifications,
    achievements, languages, links - never penalizes missing "professional
    experience" on its own."""
    score = 0
    if sections_report.get("education") in ("detected", "possibly_detected"):
        score += 20
    if sections_report.get("projects") == "detected":
        score += 20
    elif sections_report.get("projects") == "possibly_detected":
        score += 10
    if sections_report.get("internships") in ("detected", "possibly_detected"):
        score += 15
    if len(parsed.get("skills", [])) >= 5:
        score += 20
    elif parsed.get("skills"):
        score += 10
    if sections_report.get("certifications") in ("detected", "possibly_detected"):
        score += 10
    if sections_report.get("achievements") in ("detected", "possibly_detected"):
        score += 5
    contact = parsed.get("contact", {})
    if contact.get("github") or contact.get("portfolio"):
        score += 10
    return min(100, score)


def _ats_compatibility(parsed, sections_report, formatting_result):
    score = 0
    text_ok = bool(parsed.get("text", "").strip())
    score += 25 if text_ok else 0

    contact = parsed.get("contact", {})
    contact_fields_present = sum(1 for v in (contact.get("email"), contact.get("phone")) if v)
    score += round(contact_fields_present / 2 * 20)

    detected_sections = sum(1 for v in sections_report.values() if v in ("detected", "possibly_detected"))
    score += round(min(detected_sections, 6) / 6 * 25)

    score += 15 if parsed.get("skills") else 0

    score += round(formatting_result["score"] / 100 * 15)
    return min(100, score)


def _spelling_grammar(text):
    """pyspellchecker only - no paid grammar API. Only checks words that
    appear fully lowercase in the source text - this is deliberate: names,
    places, and other proper nouns are almost always capitalized in a
    resume, and pyspellchecker's dictionary doesn't know them, so checking
    capitalized words produces mostly false positives (flagging a
    candidate's own name as a "spelling mistake"). Restricting to lowercase
    tokens trades a few missed capitalized typos for a much more credible,
    low-noise report. Also skips known skill/tech terms."""
    from spellchecker import SpellChecker

    from services.skills_vocabulary import ALL_SKILLS

    # Emails/URLs are not prose - strip them first so "arunkumar" from a
    # linkedin.com/in/arunkumar link never gets treated as a misspelled word.
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\S+\.(?:com|in|io|dev|me|net|org)\S*", " ", text, flags=re.IGNORECASE)

    # Common tech/resume words missing from pyspellchecker's default English
    # dictionary - a small, hand-maintained allowlist to keep the report
    # credible rather than flagging ordinary industry vocabulary.
    extra_known_words = {
        "backend", "frontend", "fullstack", "hackathon", "onboarding", "scalable",
        "microservices", "devops", "codebase", "middleware", "runtime", "changelog",
        "roadmap", "wireframe", "responsive", "cloud-native", "multithreaded",
    }
    known_terms = {s.lower() for s in ALL_SKILLS} | extra_known_words
    checker = SpellChecker(distance=1)

    words = re.findall(r"[a-zA-Z]+", text)  # lowercase-only by construction
    candidates = [w for w in words if w.islower() and len(w) > 3 and w not in known_terms]
    unknown = checker.unknown([w.lower() for w in candidates])
    # Cap the list - a long resume with many proper nouns/acronyms shouldn't
    # produce an overwhelming report.
    misspelled = []
    seen = set()
    for word in candidates:
        lw = word.lower()
        if lw in unknown and lw not in seen:
            seen.add(lw)
            suggestion = checker.correction(lw)
            misspelled.append({"word": word, "suggestion": suggestion if suggestion != lw else ""})
        if len(misspelled) >= 20:
            break

    repeated_words = re.findall(r"\b(\w+)\s+\1\b", text, re.IGNORECASE)
    return {"misspelled": misspelled, "repeated_words": list(set(repeated_words))[:10]}


def analyze(parsed, profile_skills=None, has_professional_experience_elsewhere=False):
    if parsed.get("error"):
        return {
            "score": 0, "score_breakdown": {}, "issues": [
                {"priority": ISSUE_PRIORITY_HIGH, "category": "document", "message": parsed["error"]}
            ], "recommendations": [], "sections_report": {},
        }

    sections_report = _sections(parsed, has_professional_experience_elsewhere)
    formatting_result = _formatting(parsed)
    content_result = _content_quality(parsed, sections_report)
    ats_compat = _ats_compatibility(parsed, sections_report, formatting_result)
    skills_coverage = _skills_coverage(parsed, profile_skills)
    student_readiness = _student_readiness(parsed, sections_report)
    grammar_result = _spelling_grammar(parsed.get("text", ""))

    issues = list(formatting_result["issues"]) + list(content_result["issues"])
    for key, status in sections_report.items():
        if status == "missing" and key in ("skills", "education"):
            issues.append({
                "priority": ISSUE_PRIORITY_HIGH, "category": "sections",
                "message": f"No {key.title()} section detected on the resume.",
            })
        elif status == "missing" and key in ("languages", "achievements"):
            # Low priority: unlike Skills/Education, a resume is not broken
            # for lacking these - just worth flagging (spec section 9/10).
            issues.append({
                "priority": ISSUE_PRIORITY_LOW, "category": "sections",
                "message": f"No dedicated {key.title()} section detected on the resume.",
            })

    # Section headings recognized only by fuzzy match (spec sections 4/13):
    # never silently "fixed", never reported missing - just flagged so the
    # candidate can correct the spelling if they choose to.
    for key, heading_info in parsed.get("section_headings", {}).items():
        if heading_info.get("is_exact"):
            continue
        heading_text = heading_info["heading"]
        canonical = heading_info["canonical"].upper()
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "spelling", "section": key,
            "text": heading_text,
            "message": f'Section heading "{heading_text}" contains a spelling variation.',
            "suggestion": f'Suggested correction: "{canonical}"',
        })
    if grammar_result["misspelled"]:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "grammar",
            "message": f"{len(grammar_result['misspelled'])} possible spelling issue(s) detected.",
        })
    if grammar_result["repeated_words"]:
        issues.append({
            "priority": ISSUE_PRIORITY_LOW, "category": "grammar",
            "message": "Repeated consecutive words detected (e.g. \"the the\").",
        })

    recommendations = list(content_result["recommendations"])
    if not parsed.get("contact", {}).get("linkedin"):
        recommendations.append("Add your LinkedIn profile URL - most recruiters check it.")
    if not parsed.get("skills"):
        recommendations.append("Add a dedicated Skills section listing your key technical/professional skills.")
    if not parsed.get("contact", {}).get("phone"):
        recommendations.append("Add a phone number so recruiters can reach you directly.")

    # Recommendations must come from real detected issues (spec section
    # 10), not a separate hand-picked list - reuse the section-related and
    # spelling-variation issues just built above instead of duplicating
    # their logic.
    for issue in issues:
        if issue["category"] == "spelling" and "text" in issue:
            recommendations.append(
                f'"{issue["text"]}" appears to be a spelling variation of a standard section heading '
                f'({issue["suggestion"].split(": ", 1)[-1]}). Consider correcting it.'
            )
        elif issue["category"] == "sections" and issue["priority"] == ISSUE_PRIORITY_LOW:
            recommendations.append(
                issue["message"] + " Consider adding one if relevant to your profile."
            )

    breakdown = {
        "ats_compatibility": ats_compat,
        "content_quality": content_result["score"],
        "skills_coverage": skills_coverage,
        "impact": round(
            (content_result["bullet_stats"]["with_quantification"] /
             content_result["bullet_stats"]["count"] * 100)
            if content_result["bullet_stats"]["count"] else 0
        ),
        "formatting": formatting_result["score"],
        "student_readiness": student_readiness,
    }
    overall = round(
        breakdown["ats_compatibility"] * 0.25
        + breakdown["content_quality"] * 0.2
        + breakdown["skills_coverage"] * 0.2
        + breakdown["impact"] * 0.1
        + breakdown["formatting"] * 0.15
        + breakdown["student_readiness"] * 0.1
    )

    issue_order = {ISSUE_PRIORITY_HIGH: 0, ISSUE_PRIORITY_MEDIUM: 1, ISSUE_PRIORITY_LOW: 2}
    issues.sort(key=lambda i: issue_order.get(i["priority"], 3))

    return {
        "score": max(0, min(100, overall)),
        "score_breakdown": breakdown,
        "issues": issues,
        "recommendations": recommendations,
        "sections_report": sections_report,
        "grammar": grammar_result,
    }

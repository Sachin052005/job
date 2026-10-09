"""Chat for Help - the ONLY AI feature in TalentPanda. Answers questions about
using the portal itself (never career advice, resume scoring, ATS, or AI job
matching). Talks to a locally/remotely running Ollama server.

Every failure mode - unreachable server, timeout, connection refused, model
not found, empty/invalid/malformed response - degrades to a friendly
"unavailable" message; the caller (the view) is guaranteed a (reply, error)
tuple and never an exception. Technical detail is logged server-side only.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
# A cold/first generation on modest local hardware can take 30s+ (observed
# ~32s against llama3.2:latest during verification) - 20s was tight enough
# to cause false "unavailable" failures on a real request. Still bounded -
# never hangs indefinitely.
REQUEST_TIMEOUT_SECONDS = 60
MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_TURNS = 6

UNAVAILABLE_MESSAGE = (
    "Sorry, the help assistant is temporarily unavailable. Please make sure Ollama is running and try again."
)
OFF_TOPIC_MESSAGE = (
    "I'm here to help you use TalentPanda. I can help with jobs, applications, profiles, companies, "
    "settings, notifications, and other TalentPanda features."
)
CAREER_ADVICE_REDIRECT_MESSAGE = (
    "I can help you use TalentPanda, such as searching for jobs, applying, updating your profile, "
    "saving jobs, or creating job alerts."
)

# Real routes only (spec section 18: "Do NOT hallucinate routes") - kept next
# to the prompt so the two never drift apart. Update this alongside
# config/urls.py / app urls.py if routes change.
PORTAL_ROUTES = """
- Home / job search: /
- Browse & search jobs: /jobs/
- Job detail page: /jobs/<id>/
- Post a job (recruiter): /jobs/create/
- Saved Jobs: /saved-jobs/
- My Applications: /applications/
- Apply to a job: from the job detail page, "Apply" or "Easy Apply" (Easy Apply only shows if the recruiter enabled it and the candidate's profile has a resume and skills)
- Job Alerts: /job-alerts/
- Companies: /companies/
- Followed Companies: /companies/followed/
- Company profile (recruiter): /companies/create/ or /companies/<slug>/edit/
- Notifications: /notifications/
- Candidate profile: /accounts/profile/ (view), /accounts/profile/edit/ (edit)
- Recruiter profile: /accounts/recruiter/profile/
- Register: /accounts/register/
- Login: /accounts/login/ (has "Continue with Google" when Google sign-in is configured)
- Forgot password: /accounts/password/reset/
- Dashboard: /dashboard/
- Settings home: /settings/
- Settings > Account: /settings/account/
- Settings > Security (change password, link Google): /settings/security/password/
- Settings > Appearance (Light/Dark/System theme): /settings/appearance/
- Settings > Notifications (per-category toggles): /settings/notifications/
- Settings > Privacy (profile visibility, recruiter search/contact/resume download): /settings/privacy/
- Settings > Application Preferences (preferred domain/location/salary/work mode/employment type/notice period): /settings/application-preferences/
- FAQs: /help/faq/
- Feedback: /help/feedback/
- Chat for Help (this chat): /help/chat/
- About: /about/
""".strip()

SYSTEM_PROMPT = f"""You are the TalentPanda Help Assistant.

You help users understand and use the TalentPanda job portal. You answer
questions about: registration, login, Google login, forgot password, profile,
profile completion, profile settings, jobs, job search, job filters,
recommended jobs, saving jobs, saved jobs, job alerts, applications, Easy
Apply, normal Apply, application status, screening questions, interviews,
notifications, companies, following companies, recruiter features, recruiter
profile, company profile, posting jobs, managing jobs, candidates, recruiter
application management, settings, appearance, dark mode, light mode, system
theme, privacy, application preferences, feedback, FAQ, account settings,
security, and general TalentPanda navigation.

Give clear, step-by-step instructions grounded in the portal's actual pages
and buttons. Use ONLY the real routes/features listed below - never invent a
page or URL that isn't listed.

Known TalentPanda routes/features:
{PORTAL_ROUTES}

Example:
User: "How do I save a job?"
Answer: "Open the job you are interested in and click the Save button. You can later find it under Saved Jobs."

User: "How do I apply?"
Answer: "Open the job details page. If the employer enabled Easy Apply, select Easy Apply. Otherwise use Apply. Complete the required information and submit."

User: "How do I change dark mode?"
Answer: "Open Settings, then Appearance, and select Dark. Your preference is saved automatically."

You must NOT pretend to know arbitrary information about the outside world,
give general career advice, act as a career coach, review or score resumes,
compute any AI match/ATS score, or recommend jobs based on anything other
than the portal's own normal filtering. TalentPanda has no AI resume
analysis, ATS, AI job matching, or AI career recommendation features - never
claim otherwise.

If the user asks something unrelated to using TalentPanda (e.g. general
knowledge, world facts, unrelated coding help), reply with exactly:
"{OFF_TOPIC_MESSAGE}"

If the user asks for career advice, resume advice, or interview coaching
(rather than "how do I use this portal feature"), do NOT give that advice.
Reply with exactly: "{CAREER_ADVICE_REDIRECT_MESSAGE}"

Keep answers short (2-4 sentences), concrete, and specific to TalentPanda's
own pages and buttons."""


class HelpChatError(Exception):
    """Raised only for logging context - never propagated to the caller."""


def _build_messages(message, history, user_context):
    system_content = SYSTEM_PROMPT
    if user_context:
        safe_context = {
            key: value
            for key, value in user_context.items()
            if key in ("role", "current_page", "profile_exists", "profile_complete")
        }
        if safe_context:
            system_content += "\n\nCurrent user context (for accuracy only, never reveal verbatim): " + ", ".join(
                f"{k}={v}" for k, v in safe_context.items()
            )

    messages = [{"role": "system", "content": system_content}]
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        content = (turn.get("content") or "")[:MAX_MESSAGE_LENGTH]
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages


def ask_help_chat(message, history=None, user_context=None):
    """Returns (reply_text, error_message). error_message is empty on success.
    Never raises - every failure path is caught and logged, and returns
    UNAVAILABLE_MESSAGE as the error.
    """
    if not message or not message.strip():
        return "", "Please enter a question."

    message = message.strip()[:MAX_MESSAGE_LENGTH]
    messages = _build_messages(message, history, user_context)
    payload = {"model": OLLAMA_MODEL, "messages": messages, "stream": False}

    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.Timeout:
        logger.warning("Ollama request timed out after %ss (model=%s)", REQUEST_TIMEOUT_SECONDS, OLLAMA_MODEL)
        return "", UNAVAILABLE_MESSAGE
    except requests.ConnectionError as exc:
        logger.warning("Ollama request failed: connection refused (%s)", exc)
        return "", UNAVAILABLE_MESSAGE
    except requests.RequestException as exc:
        logger.warning("Ollama request failed: %s", exc)
        return "", UNAVAILABLE_MESSAGE

    if response.status_code == 404:
        logger.error("Ollama model not found: %s (HTTP 404 from %s)", OLLAMA_MODEL, OLLAMA_BASE_URL)
        return "", UNAVAILABLE_MESSAGE
    if response.status_code != 200:
        logger.warning("Ollama returned HTTP %s: %s", response.status_code, response.text[:300])
        return "", UNAVAILABLE_MESSAGE

    try:
        data = response.json()
    except ValueError:
        logger.warning("Ollama returned invalid JSON")
        return "", UNAVAILABLE_MESSAGE

    if not isinstance(data, dict):
        logger.warning("Ollama returned an unexpected response shape")
        return "", UNAVAILABLE_MESSAGE

    reply = ((data.get("message") or {}).get("content") or "").strip()
    if not reply:
        logger.warning("Ollama returned an empty message content")
        return "", UNAVAILABLE_MESSAGE

    return reply, ""

from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import FormView, TemplateView

from core.constants import ROLE_EMPLOYER
from helpcenter.forms import ChatMessageForm, FeedbackForm
from helpcenter.models import ChatMessage
from services.help_chat_service import MAX_MESSAGE_LENGTH, ask_help_chat

# Real, TalentPanda-specific FAQ content, organized under the tab keys the
# navbar mega menu already links to (help:faq?tab=<key>) - kept stable so
# those links (and any bookmarked ones) keep working. Every answer describes
# actual platform behavior only; every action link points at a real,
# reversible URL name.
FAQ_DATA = {
    "jobs": {
        "label": "Job Search",
        "items": [
            {
                "q": "How do I search for a job?",
                "a": "Use the keyword search in the navbar (job title, skills, or company) or open the Jobs page directly - both use the same job search engine.",
                "action_label": "Browse Jobs", "action_url": "jobs:list",
            },
            {
                "q": "How do I filter jobs by domain or subdomain?",
                "a": "On the Jobs page, use the Domain and Subdomain filters in the Filters panel. Subdomain options update to match whichever domain (IT, Non-IT, or Medical Coding) you pick, and the results only ever include jobs from that domain/subdomain.",
                "action_label": "Browse Jobs", "action_url": "jobs:list",
            },
            {
                "q": "How do I search for fresher jobs?",
                "a": "Turn on the \"Freshers\" checkbox in the Jobs page filters, or use the Fresher Jobs link in the Jobs menu. This shows jobs marked \"Freshers Can Apply\" or that require 0 years of experience.",
            },
            {
                "q": "How do I find remote jobs?",
                "a": "Turn on the \"Remote\" checkbox in the Jobs page filters. This shows jobs whose work mode is Remote or that carry a Remote badge.",
            },
            {
                "q": "How do I find urgent or walk-in jobs?",
                "a": "Turn on the \"Urgent\" or \"Walk-in\" checkboxes in the Jobs page filters. These match jobs the recruiter tagged with the Urgent Hiring or Walk-in Interview badge.",
            },
        ],
    },
    "applications": {
        "label": "Applications",
        "items": [
            {
                "q": "How do I apply for a job?",
                "a": "Open a job's detail page and click Apply (fills out a full application) or Easy Apply (reuses your saved profile), whichever the recruiter has enabled for that job.",
                "action_label": "Browse Jobs", "action_url": "jobs:list",
            },
            {
                "q": "Where can I see my applications?",
                "a": "My Applications lists every job you've applied to along with its current status.",
                "action_label": "My Applications", "action_url": "applications:mine",
            },
            {
                "q": "What does \"Under Review\" mean?",
                "a": "The recruiter has received your application and hasn't moved it to Shortlisted, Interview, or Rejected yet.",
            },
            {
                "q": "What does \"Shortlisted\" mean?",
                "a": "The recruiter has flagged your application as a strong match and is considering you for the next step (often an interview).",
            },
            {
                "q": "How do I know if the recruiter changed my application status?",
                "a": "You'll get a notification, and the change also appears on your Profile Performance timeline under Recruiter Actions - both are driven by the same status change, so they always agree.",
                "action_label": "View Performance", "action_url": "accounts:performance",
            },
        ],
    },
    "resume": {
        "label": "Resume & ATS",
        "items": [
            {
                "q": "How do I upload my resume?",
                "a": "Go to your Profile and open the Resume section to upload a PDF or DOCX file - it replaces the version recruiters see on your applications going forward.",
                "action_label": "Update Profile", "action_url": "accounts:profile_edit",
            },
            {
                "q": "What is Resume ATS Check?",
                "a": "Resume ATS Check (also called Resume Health) scans your uploaded resume for structural and content issues - missing sections, formatting problems, weak bullet points - independent of any specific job.",
                "action_label": "Check My Resume", "action_url": "resumes:list",
            },
            {
                "q": "What is Job Match ATS Check?",
                "a": "Job Match ATS Check compares your resume against a specific job's description and shows which required skills you already have and which ones are missing for that role.",
                "action_label": "Check My Resume", "action_url": "resumes:list",
            },
            {
                "q": "Why does my ATS result change for different jobs?",
                "a": "Resume ATS Check scores your resume on its own. Job Match ATS Check scores it against one job's specific requirements, so the same resume can match one job closely and another job less closely.",
            },
            {
                "q": "How can I fix an ATS issue?",
                "a": "Open the issue on your Resume ATS Check results - each one names the section or problem (e.g. a missing section, or a skill the job needs) so you know exactly what to update, then re-upload your resume.",
                "action_label": "Check My Resume", "action_url": "resumes:list",
            },
            {
                "q": "Can ATS automatically add skills to my resume?",
                "a": "No. ATS only compares the skills already in your resume against a job's requirements and reports what's missing - it never edits your resume or invents skills you don't have. Add a missing skill yourself only if it's genuinely true.",
            },
        ],
    },
    "account": {
        "label": "Student Account",
        "items": [
            {
                "q": "How do I update my profile?",
                "a": "Go to your Profile and use Edit Profile to update your basic details, career preferences, education, experience, projects, and skills.",
                "action_label": "Update Profile", "action_url": "accounts:profile_edit",
            },
            {
                "q": "How does profile completion work?",
                "a": "Your profile page shows a completion percentage based on filled-in sections (basic details, career preferences, education, skills, resume, and more). Completing more sections raises the percentage and makes your profile more visible to recruiters.",
                "action_label": "Update Profile", "action_url": "accounts:profile_edit",
            },
            {
                "q": "What is Search Appearance?",
                "a": "A Search Appearance is logged whenever your profile shows up in a recruiter's candidate search results. It's tracked separately from Profile Views (which count only when a recruiter actually opens your profile).",
                "action_label": "View Performance", "action_url": "accounts:performance",
            },
            {
                "q": "Why did my recruiter activity count change?",
                "a": "Recruiter Actions on your Profile Performance page counts real events - profile views, search appearances, resume views/downloads, shortlists, interviews, and application status changes - for whichever date range you have selected. Changing the range changes the count.",
                "action_label": "View Performance", "action_url": "accounts:performance",
            },
            {
                "q": "Can recruiters see my profile even if I don't want them to?",
                "a": "No. Recruiters can only find you in candidate search, view your profile, or download your resume if your Privacy settings allow it - you control each of those independently.",
                "action_label": "Privacy Settings", "action_url": "settings:privacy",
            },
        ],
    },
    "job_seeker": {
        "label": "Job Seeker Help",
        "items": [
            {
                "q": "How do I use Easy Apply?",
                "a": "Complete your profile once (resume, phone, location, skills, and social links) so it meets the Easy Apply requirements. On any job that supports it, Easy Apply then reuses that saved profile instead of a fresh form.",
                "action_label": "Update Profile", "action_url": "accounts:profile_edit",
            },
            {
                "q": "How do I save a job for later?",
                "a": "Click the bookmark button on any job card or job detail page. Find every saved job again under Saved Jobs in the Jobs menu.",
                "action_label": "Saved Jobs", "action_url": "saved_jobs:list",
            },
            {
                "q": "How do I create a job alert?",
                "a": "Go to Job Alerts and create one with your keyword, location, experience, and salary criteria - you'll be notified as matching jobs are posted.",
                "action_label": "Job Alerts", "action_url": "job_alerts:list",
            },
            {
                "q": "How do I follow a company?",
                "a": "Open a company's page and click Follow. You'll be notified when that company posts new jobs.",
                "action_label": "Explore Companies", "action_url": "companies:list",
            },
        ],
    },
    "recruiter": {
        "label": "Recruiter",
        "items": [
            {
                "q": "How can recruiters search candidates?",
                "a": "Candidate Search lets you filter job seekers by name, skills, location, experience, education, and career preferences - only candidates who have opted in to recruiter search appear in results.",
                "action_label": "Search Candidates", "action_url": "students:search",
            },
            {
                "q": "What happens when a recruiter views my profile?",
                "a": "A Profile View is logged on the candidate's activity timeline and they're notified, unless you already viewed that same candidate's profile recently (repeat views within the same day don't create duplicates).",
            },
            {
                "q": "What is Search Appearance?",
                "a": "Whenever your candidate search results include a student, that's logged as a Search Appearance on their side - it's how students know their profile is being discovered, distinct from you actually opening their profile.",
            },
            {
                "q": "Can recruiters view my resume?",
                "a": "Only if that candidate's privacy settings allow recruiters to view or download resumes. When allowed, opening or downloading a candidate's resume is logged on their activity timeline.",
            },
            {
                "q": "How do I review applicants?",
                "a": "Open Manage Jobs, pick a job, then View Applicants to see and filter every candidate who applied.",
                "action_label": "Manage Jobs", "action_url": "dashboard:home",
            },
            {
                "q": "How do I change an applicant's status?",
                "a": "On an application's detail page, use the Update Status panel to move it through Under Review, Shortlisted, Interview, Selected, Hired, or Rejected - the applicant is notified of the change automatically.",
            },
        ],
    },
    "company": {
        "label": "Company",
        "items": [
            {
                "q": "How do I update my company profile?",
                "a": "Go to Manage Company to update your company's details, locations, salary bands, and products/services.",
                "action_label": "Manage Company", "action_url": "companies:manage",
            },
            {
                "q": "How do I post a job?",
                "a": "Create your company profile first if you haven't, then use Post a Job to publish a listing under one of the fixed domains (IT, Non-IT, or Medical Coding) and its subdomain.",
                "action_label": "Post a Job", "action_url": "jobs:create",
            },
            {
                "q": "How do I manage applications?",
                "a": "Open Manage Jobs, pick a job, then View Applicants to review, filter, and update the status of everyone who applied.",
                "action_label": "Manage Jobs", "action_url": "dashboard:home",
            },
            {
                "q": "How do I search candidates?",
                "a": "Candidate Search lets you filter job seekers by skills, location, experience, and education - only candidates who've opted in to recruiter search appear.",
                "action_label": "Search Candidates", "action_url": "students:search",
            },
        ],
    },
}


class FeedbackCreateView(FormView):
    template_name = "helpcenter/feedback.html"
    form_class = FeedbackForm
    success_url = "/help/feedback/"

    def form_valid(self, form):
        feedback = form.save(commit=False)
        if self.request.user.is_authenticated:
            feedback.user = self.request.user
        feedback.save()
        messages.success(self.request, "Thank you for your feedback.")
        return super().form_valid(form)


class FAQView(TemplateView):
    template_name = "helpcenter/faq.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["faq_data"] = FAQ_DATA
        tab = self.request.GET.get("tab", "job_seeker")
        context["tab"] = tab if tab in FAQ_DATA else "job_seeker"
        return context


class AboutView(TemplateView):
    template_name = "helpcenter/about.html"


class ChatView(TemplateView):
    """Chat for Help - the only AI feature in TalentPanda.

    GET renders the page (server-rendered history so it works with JS
    disabled). POST is an AJAX/JSON endpoint: the page's own JS calls it with
    fetch() and renders the answer in place - no full page reload, and the
    browser never sees raw Ollama JSON or a Python traceback (see
    ask_help_chat, which never raises).
    """

    template_name = "helpcenter/chat.html"
    SESSION_KEY = "help_chat_history"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        history = self.request.session.get(self.SESSION_KEY)
        if not history and self.request.user.is_authenticated:
            # Hydrate from persisted history (spec section 20) so a returning
            # user sees continuity even in a fresh browser session.
            recent = list(
                ChatMessage.objects.filter(user=self.request.user).order_by("-created_at")[:10]
            )[::-1]
            history = []
            for entry in recent:
                history.append({"role": "user", "content": entry.question})
                history.append({"role": "assistant", "content": entry.answer})
            self.request.session[self.SESSION_KEY] = history
        context["history"] = history or []
        context["form"] = ChatMessageForm()
        return context

    def _user_context(self, request):
        profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
        if not profile:
            return None
        return {
            "role": "recruiter" if profile.role == ROLE_EMPLOYER else "student",
            "current_page": request.META.get("HTTP_REFERER", "")[:200] or "/help/chat/",
            "profile_exists": True,
            "profile_complete": profile.completion_percent() >= 80,
        }

    def post(self, request, *args, **kwargs):
        # AJAX-only endpoint: browsers with JS disabled still get a working
        # page via GET (server-rendered history) but can't post - acceptable
        # given Chat for Help is inherently an interactive feature.
        form = ChatMessageForm(request.POST)
        if not form.is_valid():
            error = next(iter(form.errors.get("message", [])), "Please enter a valid question.")
            return JsonResponse({"success": False, "error": error}, status=400)

        question = form.cleaned_data["message"][:MAX_MESSAGE_LENGTH]
        history = request.session.get(self.SESSION_KEY, [])
        reply, error = ask_help_chat(question, history, self._user_context(request))
        answer = error or reply

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        request.session[self.SESSION_KEY] = history[-20:]
        request.session.modified = True

        if request.user.is_authenticated:
            ChatMessage.objects.create(user=request.user, question=question, answer=answer)

        if error:
            return JsonResponse({"success": False, "error": error})
        return JsonResponse({"success": True, "answer": answer})

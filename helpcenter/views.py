from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import FormView, TemplateView

from core.constants import ROLE_EMPLOYER
from helpcenter.forms import ChatMessageForm, FeedbackForm
from helpcenter.models import ChatMessage
from services.help_chat_service import MAX_MESSAGE_LENGTH, ask_help_chat

FAQ_DATA = {
    "job_seeker": [
        ("How do I apply for a job?", "Open a job's detail page and click Apply (full form) or Easy Apply (uses your saved profile) if the recruiter has enabled it."),
        ("How do I use Easy Apply?", "Complete your profile (resume + skills) once. Then Easy Apply on any job that supports it pre-fills your details - review and submit."),
        ("How do I save a job for later?", "Click the Save button on any job card or job detail page. Find it again under Saved Jobs in the Jobs menu."),
        ("How do I create a job alert?", "Go to Jobs > Job Alerts, click Create, and set your keywords/location/experience/salary criteria."),
        ("How do I follow a company?", "Open a company's page and click Follow. You'll be notified when they post new jobs."),
    ],
    "recruiter": [
        ("How do I post a job?", "Go to Jobs > Post a Job (create your company profile first if you haven't)."),
        ("How do I review applicants?", "Open Manage Jobs, pick a job, then View Applicants to see and filter candidates."),
        ("How do I change an applicant's status?", "On an application's detail page, use the Update Status panel."),
    ],
    "company": [
        ("How do I create my company profile?", "As a recruiter, go to Companies > Post a Job, which will prompt you to create your company profile first."),
        ("How do I verify my company?", "Upload your business proof document from your Company Profile page; verification status is shown there."),
    ],
    "applications": [
        ("Where can I see my applications?", "Go to Jobs > My Applications to see every application and its status."),
        ("What do application statuses mean?", "Applied, Under Review, Shortlisted, Interview, Selected, and Rejected reflect where the recruiter is in their process."),
    ],
    "account": [
        ("How do I change my password?", "Go to Settings > Security and use the Change Password form."),
        ("How do I switch between light and dark mode?", "Go to Settings > Appearance and choose Light, Dark, or System."),
    ],
    "jobs": [
        ("How do I search for jobs?", "Use the search bar on the Home page or Jobs page, and narrow results with the filters."),
        ("What does 'Urgent Hiring' mean?", "It's a badge the recruiter chose to highlight that they're hiring quickly for that role."),
    ],
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
        context["tab"] = self.request.GET.get("tab", "job_seeker")
        return context


class AboutView(TemplateView):
    template_name = "helpcenter/about.html"


class ChatView(TemplateView):
    """Chat for Help - the only AI feature in NammaCareer.

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

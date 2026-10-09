import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpcenter.models import ChatMessage, Feedback
from services.help_chat_service import (
    MAX_MESSAGE_LENGTH,
    OFF_TOPIC_MESSAGE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    UNAVAILABLE_MESSAGE,
    ask_help_chat,
)

User = get_user_model()


class FeedbackTests(TestCase):
    def test_anonymous_can_submit_feedback(self):
        response = self.client.post(
            reverse("help:feedback"), {"rating": 5, "category": "website", "message": "Great site"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertIsNone(Feedback.objects.first().user)

    def test_authenticated_feedback_attached_to_user(self):
        user = User.objects.create_user(username="feedbacker", password="pass12345")
        self.client.login(username="feedbacker", password="pass12345")
        self.client.post(reverse("help:feedback"), {"rating": 4, "category": "jobs", "message": "Good"})
        self.assertEqual(Feedback.objects.first().user, user)


class FAQTests(TestCase):
    def test_faq_page_loads_and_switches_tabs(self):
        response = self.client.get(reverse("help:faq"), {"tab": "recruiter"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How do I post a job?")


class ChatServiceTests(TestCase):
    """services/help_chat_service.py - all mocked, no real Ollama server needed."""

    @patch("services.help_chat_service.requests.post")
    def test_uses_configured_base_url_and_model(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": {"content": "Click Save on the job."}}
        ask_help_chat("How do I save a job?")
        called_url = mock_post.call_args.args[0]
        called_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(called_url, f"{OLLAMA_BASE_URL}/api/chat")
        self.assertEqual(called_payload["model"], OLLAMA_MODEL)
        self.assertFalse(called_payload["stream"])

    @patch("services.help_chat_service.requests.post")
    def test_ask_help_chat_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": {"content": "Click Apply on the job page."}}
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(error, "")
        self.assertIn("Apply", reply)

    @patch("services.help_chat_service.requests.post")
    def test_empty_ollama_message_content_is_handled(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"message": {"content": ""}}
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(reply, "")
        self.assertEqual(error, UNAVAILABLE_MESSAGE)

    @patch("services.help_chat_service.requests.post")
    def test_timeout_is_handled(self, mock_post):
        import requests

        mock_post.side_effect = requests.Timeout("timed out")
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(reply, "")
        self.assertEqual(error, UNAVAILABLE_MESSAGE)

    @patch("services.help_chat_service.requests.post")
    def test_connection_refused_is_handled(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("connection refused")
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(reply, "")
        self.assertEqual(error, UNAVAILABLE_MESSAGE)

    @patch("services.help_chat_service.requests.post")
    def test_model_not_found_is_handled(self, mock_post):
        mock_post.return_value.status_code = 404
        mock_post.return_value.text = "model not found"
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(reply, "")
        self.assertEqual(error, UNAVAILABLE_MESSAGE)

    @patch("services.help_chat_service.requests.post")
    def test_invalid_json_is_handled(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = ValueError("bad json")
        reply, error = ask_help_chat("How do I apply?")
        self.assertEqual(reply, "")
        self.assertEqual(error, UNAVAILABLE_MESSAGE)

    def test_ask_help_chat_rejects_empty_message(self):
        reply, error = ask_help_chat("   ")
        self.assertEqual(reply, "")
        self.assertTrue(error)

    def test_message_truncated_to_max_length(self):
        with patch("services.help_chat_service.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"message": {"content": "ok"}}
            ask_help_chat("x" * (MAX_MESSAGE_LENGTH + 500))
            sent_messages = mock_post.call_args.kwargs["json"]["messages"]
            user_turn = [m for m in sent_messages if m["role"] == "user"][-1]
            self.assertLessEqual(len(user_turn["content"]), MAX_MESSAGE_LENGTH)

    def test_system_prompt_references_real_routes(self):
        # Guards against route hallucination (spec section 18): the prompt
        # must reference actual app routes, not made-up ones.
        from services.help_chat_service import SYSTEM_PROMPT

        self.assertIn("/saved-jobs/", SYSTEM_PROMPT)
        self.assertIn("/settings/appearance/", SYSTEM_PROMPT)
        self.assertIn("/job-alerts/", SYSTEM_PROMPT)


class ChatViewTests(TestCase):
    def test_chat_page_loads(self):
        response = self.client.get(reverse("help:chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ask a question about using TalentPanda")

    @patch("helpcenter.views.ask_help_chat")
    def test_valid_question_returns_clean_json(self, mock_ask):
        mock_ask.return_value = ("Use the Apply button.", "")
        response = self.client.post(
            reverse("help:chat"), {"message": "How do I apply?"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["answer"], "Use the Apply button.")
        # Never expose raw Ollama response shape to the browser.
        self.assertNotIn("message", data)
        self.assertNotIn("model", data)

    @patch("helpcenter.views.ask_help_chat")
    def test_service_error_returns_friendly_json_not_traceback(self, mock_ask):
        mock_ask.return_value = ("", UNAVAILABLE_MESSAGE)
        response = self.client.post(reverse("help:chat"), {"message": "How do I apply?"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], UNAVAILABLE_MESSAGE)
        self.assertNotIn("Traceback", response.content.decode())

    def test_empty_message_rejected_with_400(self):
        response = self.client.post(reverse("help:chat"), {"message": "   "})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])

    @patch("helpcenter.views.ask_help_chat")
    def test_off_topic_question_gets_portal_scope_response(self, mock_ask):
        mock_ask.return_value = (OFF_TOPIC_MESSAGE, "")
        response = self.client.post(reverse("help:chat"), {"message": "What is the capital of France?"})
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["answer"], OFF_TOPIC_MESSAGE)

    @patch("helpcenter.views.ask_help_chat")
    def test_chat_history_saved_for_authenticated_user(self, mock_ask):
        mock_ask.return_value = ("Open Settings, then Appearance.", "")
        user = User.objects.create_user(username="chatuser", password="pass12345")
        self.client.login(username="chatuser", password="pass12345")
        self.client.post(reverse("help:chat"), {"message": "How do I change dark mode?"})
        entry = ChatMessage.objects.get(user=user)
        self.assertEqual(entry.question, "How do I change dark mode?")
        self.assertEqual(entry.answer, "Open Settings, then Appearance.")

    @patch("helpcenter.views.ask_help_chat")
    def test_anonymous_chat_not_persisted_to_db(self, mock_ask):
        mock_ask.return_value = ("Open Settings, then Appearance.", "")
        self.client.post(reverse("help:chat"), {"message": "How do I change dark mode?"})
        self.assertEqual(ChatMessage.objects.count(), 0)

    @patch("helpcenter.views.ask_help_chat")
    def test_user_context_passed_for_authenticated_recruiter(self, mock_ask):
        from core.constants import ROLE_EMPLOYER

        mock_ask.return_value = ("ok", "")
        user = User.objects.create_user(username="chatrecruiter", password="pass12345")
        user.profile.role = ROLE_EMPLOYER
        user.profile.save()
        self.client.login(username="chatrecruiter", password="pass12345")
        self.client.post(reverse("help:chat"), {"message": "How do I post a job?"})
        context_arg = mock_ask.call_args.args[2]
        self.assertEqual(context_arg["role"], "recruiter")
        self.assertNotIn("password", context_arg)

    def test_csrf_protected(self):
        from django.test import Client

        enforcing_client = Client(enforce_csrf_checks=True)
        response = enforcing_client.post(reverse("help:chat"), {"message": "How do I apply?"})
        self.assertEqual(response.status_code, 403)

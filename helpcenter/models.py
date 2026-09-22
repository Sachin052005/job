from django.conf import settings
from django.db import models

from core.constants import FEEDBACK_CATEGORY_CHOICES


class Feedback(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_entries", null=True, blank=True
    )
    rating = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=20, choices=FEEDBACK_CATEGORY_CHOICES, default="other")
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback ({self.rating}/5) from {self.user or 'anonymous'}"


class ChatMessage(models.Model):
    """One Q&A turn of Chat for Help (spec section 20). Only ever stores the
    question/answer text - never secrets, tokens, or passwords."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="help_chat_messages", null=True, blank=True
    )
    question = models.TextField()
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"ChatMessage({self.user or 'anonymous'}, {self.created_at:%Y-%m-%d %H:%M})"

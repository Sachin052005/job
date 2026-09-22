from django.contrib import admin

from helpcenter.models import ChatMessage, Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "category", "created_at"]
    list_filter = ["rating", "category"]
    search_fields = ["user__username", "message"]
    readonly_fields = ["created_at"]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ["user", "question", "created_at"]
    search_fields = ["user__username", "question", "answer"]
    readonly_fields = ["created_at"]

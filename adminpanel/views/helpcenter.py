from adminpanel.mixins import AdminDeleteView, AdminDetailView, AdminListView, FilterSpec
from core.constants import FEEDBACK_CATEGORY_CHOICES
from helpcenter.models import ChatMessage, Feedback


class FeedbackListView(AdminListView):
    model = Feedback
    page_title = "Feedback"
    search_fields = ["user__username", "message"]
    columns = [
        ("User", "user.username"),
        ("Rating", "rating"),
        ("Category", "get_category_display"),
        ("Created", "created_at"),
    ]
    filter_specs = [FilterSpec("category", "Category", FEEDBACK_CATEGORY_CHOICES)]
    row_view_url_name = "adminpanel:feedback_detail"
    row_delete_url_name = "adminpanel:feedback_delete"
    ordering = ["-created_at"]
    select_related_fields = ["user"]


class FeedbackDetailView(AdminDetailView):
    model = Feedback
    page_title = "Feedback"
    delete_url_name = "adminpanel:feedback_delete"
    list_url_name = "adminpanel:feedback_list"
    detail_fields = [
        ("User", "user.username"),
        ("Rating", "rating"),
        ("Category", "get_category_display"),
        ("Message", "message"),
        ("Created", "created_at"),
    ]


class FeedbackDeleteView(AdminDeleteView):
    model = Feedback
    page_title = "Delete Feedback"
    list_url_name = "adminpanel:feedback_list"


class ChatMessageListView(AdminListView):
    model = ChatMessage
    page_title = "Chat Messages"
    search_fields = ["user__username", "question", "answer"]
    columns = [("User", "user.username"), ("Question", "question"), ("Created", "created_at")]
    row_view_url_name = "adminpanel:chatmessage_detail"
    row_delete_url_name = "adminpanel:chatmessage_delete"
    ordering = ["-created_at"]
    select_related_fields = ["user"]


class ChatMessageDetailView(AdminDetailView):
    model = ChatMessage
    page_title = "Chat Message"
    delete_url_name = "adminpanel:chatmessage_delete"
    list_url_name = "adminpanel:chatmessage_list"
    detail_fields = [
        ("User", "user.username"),
        ("Question", "question"),
        ("Answer", "answer"),
        ("Created", "created_at"),
    ]


class ChatMessageDeleteView(AdminDeleteView):
    model = ChatMessage
    page_title = "Delete Chat Message"
    list_url_name = "adminpanel:chatmessage_list"

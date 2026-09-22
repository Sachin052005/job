from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, View

from core.constants import NOTIFICATION_TYPE_CHOICES
from notifications.models import Notification

PAGE_SIZE = 20


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).select_related(
            "job", "application", "company"
        )
        self.tab = self.request.GET.get("tab", "all")
        if self.tab != "all":
            queryset = queryset.filter(notification_type=self.tab)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tab"] = getattr(self, "tab", "all")
        context["tabs"] = [("all", "All")] + list(NOTIFICATION_TYPE_CHOICES)
        return context


class NotificationReadRedirectView(LoginRequiredMixin, View):
    """Marks a notification read then redirects to its related object (spec section 21)."""

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return redirect(notification.get_absolute_url())

    def get(self, request, pk):
        return self.post(request, pk)


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect(request.POST.get("next") or "notifications:list")


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.delete()
        messages.success(request, "Notification deleted.")
        return redirect(request.POST.get("next") or "notifications:list")

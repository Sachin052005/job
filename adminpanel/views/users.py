from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from adminpanel.forms import AdminUserCreateForm, AdminUserEditForm
from adminpanel.mixins import (
    AdminCreateView,
    AdminDeleteView,
    AdminDetailView,
    AdminListView,
    AdminRequiredMixin,
    AdminUpdateView,
    BulkAction,
    FilterSpec,
    log_admin_action,
)
from django.contrib.admin.models import CHANGE

User = get_user_model()


class UserListView(AdminListView):
    model = User
    page_title = "Users"
    search_fields = ["username", "email", "first_name", "last_name"]
    columns = [
        ("Username", "username"),
        ("Email", "email"),
        ("Name", "get_full_name"),
        ("Active", "is_active"),
        ("Staff", "is_staff"),
        ("Superuser", "is_superuser"),
        ("Date Joined", "date_joined"),
    ]
    filter_specs = [
        FilterSpec("active", "Active", [("1", "Active"), ("0", "Inactive")], lookup="is_active"),
        FilterSpec("staff", "Staff", [("1", "Staff"), ("0", "Not staff")], lookup="is_staff"),
        FilterSpec(
            "role", "Role",
            [("job_seeker", "Job Seeker"), ("employer", "Employer")],
            lookup="profile__role",
        ),
    ]
    add_url_name = "adminpanel:user_add"
    row_view_url_name = "adminpanel:user_detail"
    row_edit_url_name = "adminpanel:user_edit"
    row_delete_url_name = "adminpanel:user_delete"
    ordering = ["-date_joined"]
    select_related_fields = ["profile"]
    bulk_actions = [
        BulkAction("activate", "Activate selected"),
        BulkAction("deactivate", "Deactivate selected"),
        BulkAction("delete", "Delete selected", "btn-outline-danger"),
    ]

    def bulk_activate(self, queryset):
        queryset.update(is_active=True)

    def bulk_deactivate(self, queryset):
        queryset.exclude(pk=self.request.user.pk).update(is_active=False)

    def bulk_delete(self, queryset):
        queryset.exclude(pk=self.request.user.pk).delete()


class UserDetailView(AdminDetailView):
    model = User
    context_object_name = "user_obj"
    template_name = "adminpanel/users/detail.html"
    page_title = "User"
    edit_url_name = "adminpanel:user_edit"
    delete_url_name = "adminpanel:user_delete"
    list_url_name = "adminpanel:user_list"
    detail_fields = [
        ("Username", "username"),
        ("Email", "email"),
        ("First name", "first_name"),
        ("Last name", "last_name"),
        ("Active", "is_active"),
        ("Staff", "is_staff"),
        ("Superuser", "is_superuser"),
        ("Date joined", "date_joined"),
        ("Last login", "last_login"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.object
        ctx["profile"] = getattr(user, "profile", None)
        ctx["recruiter_profile"] = getattr(user, "recruiter_profile", None)
        ctx["company"] = getattr(user, "company", None)
        ctx["recent_applications"] = user.applications.select_related("job")[:10]
        ctx["jobs_posted"] = user.jobs.all()[:10]
        return ctx


class UserCreateView(AdminCreateView):
    model = User
    form_class = AdminUserCreateForm
    page_title = "Add User"
    list_url_name = "adminpanel:user_list"
    detail_url_name = "adminpanel:user_detail"
    success_message = "User created."


class UserUpdateView(AdminUpdateView):
    model = User
    form_class = AdminUserEditForm
    page_title = "Edit User"
    list_url_name = "adminpanel:user_list"
    detail_url_name = "adminpanel:user_detail"
    success_message = "User updated."


class UserDeleteView(AdminDeleteView):
    model = User
    page_title = "Delete User"
    list_url_name = "adminpanel:user_list"

    def post(self, request, *args, **kwargs):
        # Guard checked before Django's DeleteView.post() ever calls
        # form_valid()/self.object.delete() (spec section 16: never let the
        # logged-in superuser accidentally remove their own account).
        target = self.get_object()
        if target.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account while logged in.")
            return redirect(reverse("adminpanel:user_detail", kwargs={"pk": target.pk}))
        return super().post(request, *args, **kwargs)


class UserPasswordResetView(AdminRequiredMixin, View):
    """Reset another user's password (spec sections 16/48) - always via
    Django's SetPasswordForm/set_password(), never a plaintext field."""

    template_name = "adminpanel/generic_form.html"

    def get(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        form = SetPasswordForm(target)
        return self._render(request, target, form)

    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        form = SetPasswordForm(target, request.POST)
        if form.is_valid():
            form.save()
            log_admin_action(request, target, CHANGE, message="Password reset via admin panel.")
            messages.success(request, f"Password updated for {target.username}.")
            return redirect("adminpanel:user_detail", pk=target.pk)
        return self._render(request, target, form)

    def _render(self, request, target, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_title": f"Reset password — {target.username}",
                "back_url": reverse("adminpanel:user_detail", kwargs={"pk": target.pk}),
            },
        )

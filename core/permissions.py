from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from core.constants import ROLE_EMPLOYER, ROLE_JOB_SEEKER


def _is_admin_account(user):
    """A superuser or staff account is Admin, full stop - never Employer or
    Job Seeker, no matter what role value happens to sit on its Profile row
    (every User gets one via the post_save signal, defaulting to job_seeker,
    since Profile.role isn't normally set for admin-only accounts)."""
    return bool(user.is_staff or user.is_superuser)


def _role(user):
    """Business-profile role (job_seeker/employer) - deliberately None for
    admin accounts (see _is_admin_account) so EmployerRequiredMixin/
    JobSeekerRequiredMixin below can never match a superuser/staff account,
    even though its Profile.role defaults to job_seeker like anyone else's.
    """
    if _is_admin_account(user):
        return None
    profile = getattr(user, "profile", None)
    return profile.role if profile is not None else None


def _redirect_to_login_with_next(request):
    # django.contrib.auth.views.redirect_to_login safely builds
    # LOGIN_URL?next=<path> (it's what LoginRequiredMixin itself uses) -
    # plain redirect("accounts:login") drops the return path, which is what
    # was silently dropping `next` for JobSeekerRequiredMixin/
    # EmployerRequiredMixin-gated pages (e.g. Settings > Application
    # Preferences) while plain LoginRequiredMixin-gated pages preserved it.
    return redirect_to_login(request.get_full_path())


def _role_mismatch_message(user, label):
    if _is_admin_account(user):
        return f"Admin accounts only have access to the admin panel, not {label} pages."
    return f"Only {label}s can access this page."


def employer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if _role(request.user) != ROLE_EMPLOYER:
            raise PermissionDenied(_role_mismatch_message(request.user, "employer"))
        return view_func(request, *args, **kwargs)

    return wrapper


def job_seeker_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if _role(request.user) != ROLE_JOB_SEEKER:
            raise PermissionDenied(_role_mismatch_message(request.user, "job seeker"))
        return view_func(request, *args, **kwargs)

    return wrapper


class EmployerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _role(self.request.user) == ROLE_EMPLOYER

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return _redirect_to_login_with_next(self.request)
        raise PermissionDenied(_role_mismatch_message(self.request.user, "employer"))


class JobSeekerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return _role(self.request.user) == ROLE_JOB_SEEKER

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return _redirect_to_login_with_next(self.request)
        raise PermissionDenied(_role_mismatch_message(self.request.user, "job seeker"))


def admin_required(view_func):
    """Gate a function-based view on is_staff or is_superuser (manual admin panel).

    Mirrors employer_required/job_seeker_required above - kept here rather
    than in adminpanel/ so all role/permission gates live in one place.
    There is no separate admin login route: an unauthenticated request is
    sent to the same settings.LOGIN_URL ("accounts:login") everyone else uses.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login_with_next(request)
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Only staff accounts can access the TalentPanda admin panel.")
        return view_func(request, *args, **kwargs)

    return wrapper


class OwnerRequiredMixin:
    """Requires self.get_object() to have an `owner_field` attribute equal to request.user.

    Implemented as a dispatch() override (not test_func()) so it composes correctly
    with EmployerRequiredMixin/JobSeekerRequiredMixin: those also subclass
    UserPassesTestMixin, and a class can only have one effective test_func() in its
    MRO - stacking two test_func-based mixins would silently drop one check.
    """

    owner_field = "employer"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        owner = obj
        for part in self.owner_field.split("__"):
            owner = getattr(owner, part, None)
        if owner != request.user:
            raise PermissionDenied("You do not have permission to modify this resource.")
        return super().dispatch(request, *args, **kwargs)

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserSettings
from core.constants import THEME_CHOICES, THEME_DARK, THEME_LIGHT

User = get_user_model()


class ThemeContextProcessorTests(TestCase):
    """Anonymous visitors always render Light Mode - never a saved cookie,
    never the OS/browser preference. Authenticated users render their saved
    Appearance setting (Light or Dark - "system" no longer exists)."""

    def test_only_light_and_dark_are_selectable(self):
        self.assertEqual([value for value, _ in THEME_CHOICES], [THEME_LIGHT, THEME_DARK])

    def test_anonymous_user_always_gets_light(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_anonymous_user_with_dark_cookie_still_gets_light(self):
        self.client.cookies["tp_theme"] = "dark"
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_incognito_style_request_with_no_cookies_is_light(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_new_user_defaults_to_light(self):
        """A brand-new UserSettings row (created via the post_save signal on
        User, exactly like at registration) must default to Light - never
        the OS/browser preference, never anything else."""
        user = User.objects.create_user(username="newuser", password="pass12345")
        self.assertEqual(user.settings.theme, THEME_LIGHT)

    def test_authenticated_light_preference(self):
        user = User.objects.create_user(username="lightuser", password="pass12345")
        user.settings.theme = THEME_LIGHT
        user.settings.save()
        self.client.login(username="lightuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_authenticated_dark_preference(self):
        user = User.objects.create_user(username="darkuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()
        self.client.login(username="darkuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

    def test_legacy_system_value_renders_as_light(self):
        """A pre-migration leftover theme="system" value (bad fixture, a row
        that somehow dodged the accounts.0009 data migration, etc.) must
        never be rendered as-is - the server only ever emits "light"/"dark"."""
        user = User.objects.create_user(username="legacyuser", password="pass12345")
        UserSettings.objects.filter(user=user).update(theme="system")
        self.client.login(username="legacyuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'data-theme="system"')
        self.assertContains(response, 'data-theme="light"')

    def test_logged_out_dark_user_sees_light_on_next_anonymous_request(self):
        user = User.objects.create_user(username="logoutuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()
        self.client.login(username="logoutuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

        # A stale theme cookie (as a client-side toggle might once have written)
        # must not leak the authenticated user's Dark preference into the
        # anonymous session after logout.
        self.client.cookies["tp_theme"] = "dark"
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

    def test_anonymous_login_immediately_applies_saved_theme_on_next_response(self):
        user = User.objects.create_user(username="loginuser", password="pass12345")
        user.settings.theme = THEME_DARK
        user.settings.save()

        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="light"')

        self.client.login(username="loginuser", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'data-theme="dark"')

    def test_public_pages_all_render_light_for_anonymous(self):
        for url in [reverse("home"), reverse("jobs:list"), reverse("companies:list"), reverse("accounts:login")]:
            response = self.client.get(url)
            self.assertContains(response, 'data-theme="light"', msg_prefix=url)


class SuperuserIsAdminOnlyTests(TestCase):
    """A superuser must act only as Admin - never Job Seeker or Employer -
    even though its auto-created Profile.role defaults to job_seeker like
    any other account's (spec: "A superuser must always be treated as Admin
    even if a profile record accidentally contains a student/employer
    role"). Covers direct/bookmarked URL access, not just hidden UI."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin_root", password="pass12345", email="admin_root@example.com"
        )
        self.client.login(username="admin_root", password="pass12345")

    def test_login_routes_superuser_straight_to_admin_panel(self):
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"), {"username": "admin_root", "password": "pass12345"}
        )
        self.assertRedirects(response, reverse("adminpanel:dashboard"))

    def test_superuser_denied_job_seeker_only_page(self):
        response = self.client.get(reverse("saved_jobs:list"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_denied_employer_only_page(self):
        response = self.client.get(reverse("jobs:create"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_use_admin_panel(self):
        response = self.client.get(reverse("adminpanel:dashboard"))
        self.assertEqual(response.status_code, 200)

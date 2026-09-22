from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification
from notifications.services import create_notification

User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="candidate1", password="pass12345")

    def test_creates_notification_by_default(self):
        notification = create_notification(self.user, "system", "Hello", "World")
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.count(), 1)

    def test_respects_disabled_category(self):
        self.user.settings.notify_system = False
        self.user.settings.save()
        notification = create_notification(self.user, "system", "Hello", "World")
        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="candidate2", password="pass12345")
        self.client.force_login(self.user)

    def test_empty_state(self):
        response = self.client.get(reverse("notifications:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No notifications yet")

    def test_mark_all_read(self):
        create_notification(self.user, "system", "One")
        create_notification(self.user, "system", "Two")
        response = self.client.post(reverse("notifications:mark_all_read"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)

    def test_delete_notification(self):
        notification = create_notification(self.user, "system", "One")
        response = self.client.post(reverse("notifications:delete", kwargs={"pk": notification.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

    def test_open_marks_read_and_redirects(self):
        notification = create_notification(self.user, "system", "One")
        response = self.client.post(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

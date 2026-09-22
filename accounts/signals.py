from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import Profile, UserSettings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
        UserSettings.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def record_login_activity(sender, user, request, **kwargs):
    Profile.objects.filter(user=user).update(last_activity_at=timezone.now())

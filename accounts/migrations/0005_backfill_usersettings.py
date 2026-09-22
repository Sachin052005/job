"""Backfill UserSettings for every user that existed before that model was
added (only the post_save signal creates one automatically, and it only
fires for NEW users - accounts registered earlier never got a row, which
crashed /settings/appearance/, /settings/notifications/, and
/settings/privacy/ with RelatedObjectDoesNotExist for those users).
"""
from django.db import migrations


def backfill_user_settings(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserSettings = apps.get_model("accounts", "UserSettings")
    existing_user_ids = set(UserSettings.objects.values_list("user_id", flat=True))
    missing = User.objects.exclude(id__in=existing_user_ids)
    UserSettings.objects.bulk_create(
        [UserSettings(user=user) for user in missing],
        ignore_conflicts=True,
    )


def noop_reverse(apps, schema_editor):
    """No-op: leaving the backfilled rows in place on a rollback is harmless
    and safer than deleting user data."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_jobalert_recruiterprofile_usersettings_socialaccount"),
    ]

    operations = [
        migrations.RunPython(backfill_user_settings, noop_reverse),
    ]

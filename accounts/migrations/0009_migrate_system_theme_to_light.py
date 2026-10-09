from django.db import migrations


def convert_system_to_light(apps, schema_editor):
    """The application now supports only Light/Dark - "system" is no longer
    a valid UserSettings.theme value. Existing users who had explicitly
    chosen "system" are converted to "light" (spec: "If an existing user has
    system, convert it to light because the supported application themes are
    now only light/dark"). Users who already had "light" or "dark" keep
    their existing choice untouched.
    """
    UserSettings = apps.get_model("accounts", "UserSettings")
    UserSettings.objects.filter(theme="system").update(theme="light")


def revert_light_to_system(apps, schema_editor):
    # Irreversible by design: we have no record of which "light" rows used
    # to be "system" before this migration ran, so there is nothing
    # meaningful to roll back to. Intentionally a no-op rather than guessing.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_alter_usersettings_theme"),
    ]

    operations = [
        migrations.RunPython(convert_system_to_light, revert_light_to_system),
    ]

"""Idempotently create a Django superuser for local development.

Reads credentials from environment variables, falling back to safe local
defaults. Run with:
    python scripts/create_admin.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()


def create_admin():
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@naukri.local")
    password = os.getenv("ADMIN_PASSWORD", "AdminPass123!")

    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    user.is_staff = True
    user.is_superuser = True
    if created or os.getenv("ADMIN_RESET_PASSWORD") == "1":
        user.set_password(password)
    user.save()

    if created:
        print(f"Created superuser '{username}' with password '{password}'.")
    else:
        print(f"Superuser '{username}' already exists; ensured staff/superuser flags are set.")


if __name__ == "__main__":
    create_admin()

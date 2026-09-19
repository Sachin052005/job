"""Bulk-import jobs from a JSON file into an existing employer's company.

Usage:
    python scripts/import_jobs.py path/to/jobs.json --employer-username acme_hr

Expected JSON shape: a list of objects with keys matching Job model fields
(title, location, description, skills, employment_type, experience_min,
experience_max, salary_min, salary_max, category [category name, optional]).
"""
import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from core.constants import JOB_STATUS_DRAFT  # noqa: E402
from jobs.models import Category, Job  # noqa: E402

User = get_user_model()


def import_jobs(json_path, employer_username):
    employer = User.objects.get(username=employer_username)
    if not hasattr(employer, "company"):
        raise SystemExit(f"User '{employer_username}' has no company profile; create one first.")

    with open(json_path, encoding="utf-8") as f:
        records = json.load(f)

    created_count = 0
    for record in records:
        category = None
        category_name = record.get("category")
        if category_name:
            category, _ = Category.objects.get_or_create(name=category_name)

        _, created = Job.objects.get_or_create(
            title=record["title"],
            company=employer.company,
            defaults={
                "employer": employer,
                "category": category,
                "location": record.get("location", ""),
                "description": record.get("description", ""),
                "responsibilities": record.get("responsibilities", ""),
                "skills": record.get("skills", ""),
                "employment_type": record.get("employment_type", "full_time"),
                "experience_min": record.get("experience_min", 0),
                "experience_max": record.get("experience_max", 0),
                "salary_min": record.get("salary_min"),
                "salary_max": record.get("salary_max"),
                "status": record.get("status", JOB_STATUS_DRAFT),
            },
        )
        if created:
            created_count += 1

    print(f"Imported {created_count} new job(s) out of {len(records)} record(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Path to a JSON file containing a list of job records.")
    parser.add_argument("--employer-username", required=True, help="Username of the employer to attribute jobs to.")
    args = parser.parse_args()
    import_jobs(args.json_path, args.employer_username)

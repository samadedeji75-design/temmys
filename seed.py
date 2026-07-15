"""
seed.py — creates the single admin account needed to log in for the first
time. Nothing else (sessions/terms/classes/subjects/teachers/students) is
seeded here — that data is expected to be created through the app itself
once an admin can log in.

Safe to re-run: looks up by email first, so it won't create a duplicate
admin or blow up on the unique constraint.

Credentials come from the environment so a real password never sits in
source control:
    ADMIN_EMAIL       (default: admin@temmys.com)
    ADMIN_PASSWORD    (required — script exits if not set)
    ADMIN_FULL_NAME   (default: School Administrator)

Usage:
    ADMIN_PASSWORD='something-strong' python seed.py
"""

import os
import sys

from app import create_app
from app.models import db, Admin


def run_seed():
    email = os.getenv("ADMIN_EMAIL", "admin@temmys.com")
    password = os.getenv("ADMIN_PASSWORD")
    full_name = os.getenv("ADMIN_FULL_NAME", "School Administrator")

    if not password:
        print("ERROR: set ADMIN_PASSWORD in the environment before running seed.py")
        sys.exit(1)

    admin = Admin.query.filter_by(email=email).first()
    if admin:
        print(f"Admin already exists ({email}) — leaving password untouched.")
        return

    admin = Admin(full_name=full_name, email=email)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin created: {email}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run_seed()
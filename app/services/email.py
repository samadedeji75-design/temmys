"""
app/services/email.py

Sends a teacher their login credentials plus the classes/subjects they're
currently assigned to, via Flask-Mail. Read-only with respect to the DB —
takes a Teacher instance and a raw (plaintext) password the caller already
has (either just-generated, or decrypted via
app.services.security.decrypt_password), and sends one email.

This module does not decide *when* to send — that's the route's job
(see app/api/routes.py: send_teacher_credentials_email). Kept separate so
the route stays thin and the email content lives in one place.
"""

from flask import current_app, url_for
from flask_mail import Message

from app import mail
from app.models import TeacherSubjectAssignment


def _teacher_assignment_lines(teacher):
    """One 'Class — Subject' line per assignment, sorted for readability."""
    assignments = (
        TeacherSubjectAssignment.query
        .filter_by(teacher_id=teacher.id)
        .join(TeacherSubjectAssignment.class_arm)
        .join(TeacherSubjectAssignment.subject)
        .all()
    )
    lines = sorted(
        f"{a.class_arm.display_name} — {a.subject.name}" for a in assignments
    )
    return lines


def send_teacher_credentials_email(teacher, raw_password):
    """
    Sends teacher.email their login (email + password) and current
    class/subject assignments. Returns True on success, False if mail
    sending failed (caller decides how to surface that to the admin —
    e.g. a toast saying the account was created/updated but the email
    didn't go out, so they can resend later).
    """
    if not teacher.email or teacher.email.endswith("@placeholder.local"):
        # Auto-generated placeholder emails (see _generate_placeholder_email
        # in app/api/routes.py) aren't real inboxes — nothing to send to
        # until the admin sets a real email on this teacher.
        return False

    assignment_lines = _teacher_assignment_lines(teacher)
    if assignment_lines:
        assignments_text = "\n".join(f"  - {line}" for line in assignment_lines)
    else:
        assignments_text = "  (No classes/subjects assigned yet.)"

    try:
        login_url = url_for("auth.teacher_login", _external=True)
    except RuntimeError:
        # url_for outside a request/app context (e.g. called from a script)
        login_url = None

    body_lines = [
        f"Hello {teacher.full_name},",
        "",
        "An account has been set up for you on the school result portal.",
        "",
        "Login details:",
        f"  Email: {teacher.email}",
        f"  Password: {raw_password}",
    ]
    if login_url:
        body_lines.append(f"  Login page: {login_url}")
    body_lines += [
        "",
        "You are currently assigned to:",
        assignments_text,
        "",
        "Please log in and keep your password confidential. If you did not "
        "expect this email, contact the school administrator.",
    ]

    message = Message(
        subject="Your Teacher Portal Login Details",
        recipients=[teacher.email],
        body="\n".join(body_lines),
    )

    try:
        mail.send(message)
        return True
    except Exception:
        current_app.logger.exception(
            "Failed to send credentials email to teacher_id=%s", teacher.id
        )
        return False
"""
app/services/email.py

Sends a teacher their login credentials plus the classes/subjects they're
currently assigned to, via the Resend HTTP API.

Switched away from Flask-Mail/SMTP: Railway (like most PaaS platforms)
blocks outbound SMTP ports (25/465/587) at the network level to prevent
spam abuse, so a raw smtplib connection just hangs until gunicorn kills
the worker on timeout — no amount of correct SMTP credentials fixes that,
since the TCP connection itself never completes. An HTTPS-based provider
sidesteps this entirely since port 443 is never blocked.

Requires RESEND_API_KEY set in the environment (get one free at
resend.com — no card required for the free tier, ~3000 emails/month).
MAIL_DEFAULT_SENDER must be a domain you've verified in Resend, OR you
can use Resend's shared onboarding domain (onboarding@resend.dev) for
testing before verifying your own domain.
"""

import requests
from flask import current_app, url_for

from app.models import TeacherSubjectAssignment

RESEND_API_URL = "https://api.resend.com/emails"


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
    class/subject assignments via Resend's HTTP API. Returns True on
    success, False if sending failed (caller decides how to surface that
    to the admin).
    """
    if not teacher.email or teacher.email.endswith("@placeholder.local"):
        # Auto-generated placeholder emails aren't real inboxes — nothing
        # to send to until the admin sets a real email on this teacher.
        return False

    api_key = current_app.config.get("RESEND_API_KEY")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    if not api_key or not sender:
        current_app.logger.error(
            "RESEND_API_KEY or MAIL_DEFAULT_SENDER not configured — cannot send email."
        )
        return False

    assignment_lines = _teacher_assignment_lines(teacher)
    if assignment_lines:
        assignments_html = "".join(f"<li>{line}</li>" for line in assignment_lines)
    else:
        assignments_html = "<li>(No classes/subjects assigned yet.)</li>"

    try:
        login_url = url_for("auth.teacher_login", _external=True)
    except RuntimeError:
        login_url = None

    login_line = f'<p>Login page: <a href="{login_url}">{login_url}</a></p>' if login_url else ""

    html_body = f"""
        <p>Hello {teacher.full_name},</p>
        <p>An account has been set up for you on the school result portal.</p>
        <p><b>Login details:</b><br>
           Email: {teacher.email}<br>
           Password: {raw_password}</p>
        {login_line}
        <p><b>You are currently assigned to:</b></p>
        <ul>{assignments_html}</ul>
        <p>Please log in and keep your password confidential. If you did not
           expect this email, contact the school administrator.</p>
    """

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": sender,
                "to": [teacher.email],
                "subject": "Your Teacher Portal Login Details",
                "html": html_body,
            },
            timeout=10,  # HTTPS call, not raw SMTP — safe to bound tightly
        )
        if response.status_code >= 400:
            current_app.logger.error(
                "Resend API error sending to teacher_id=%s: %s %s",
                teacher.id, response.status_code, response.text,
            )
            return False
        return True
    except requests.RequestException:
        current_app.logger.exception(
            "Failed to send credentials email to teacher_id=%s", teacher.id
        )
        return False

from functools import wraps
from flask import session, redirect, url_for


def teacher_required(view_func):
    """Same session check as app.admin.decorators.admin_required, scoped to
    the teacher portal — redirects to teacher login if session["teacheronline"]
    is not set."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("teacheronline") is None:
            return redirect(url_for("auth.teacher_login"))
        return view_func(*args, **kwargs)
    return wrapped
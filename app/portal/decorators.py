from functools import wraps
from flask import session, redirect, url_for


def portal_required(view_func):
    """Same pattern as app.teacher.decorators.teacher_required, scoped to
    the parent/student portal — redirects to portal login if
    session["studentonline"] is not set."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("studentonline") is None:
            return redirect(url_for("auth.portal_login"))
        return view_func(*args, **kwargs)
    return wrapped

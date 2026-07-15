from functools import wraps
from flask import session, redirect, url_for


def admin_required(view_func):
    """Same check SceneX repeats inline in every admin route
    (`if session.get('adminonline') is not None:`), wrapped as a decorator
    so it's not copy-pasted across every view function."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("adminonline") is None:
            return redirect(url_for("auth.admin_login"))
        return view_func(*args, **kwargs)
    return wrapped

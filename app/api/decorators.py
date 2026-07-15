from functools import wraps
from flask import session, jsonify


def api_admin_required(view_func):
    """Same session check as app.admin.decorators.admin_required, but
    returns a JSON 401 instead of redirecting — appropriate for endpoints
    called via fetch/$.ajax rather than a browser page load."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("adminonline") is None:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        return view_func(*args, **kwargs)
    return wrapped


def api_teacher_required(view_func):
    """Same pattern as api_admin_required, scoped to the teacher session.
    Returns a JSON 401 instead of redirecting."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("teacheronline") is None:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        return view_func(*args, **kwargs)
    return wrapped


def api_portal_required(view_func):
    """Same pattern as api_teacher_required, scoped to the portal session.
    Returns a JSON 401 instead of redirecting."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("studentonline") is None:
            return jsonify({"success": False, "message": "Not authenticated."}), 401
        return view_func(*args, **kwargs)
    return wrapped
from flask import render_template

from app.portal import portal_bp


@portal_bp.route("/dashboard")
def dashboard():
    return render_template("portal/dashboard.html")

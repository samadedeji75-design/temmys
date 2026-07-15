from flask import render_template, redirect, url_for, jsonify, request, session

from app.models import Admin, Teacher, Student
from app.auth import auth_bp
from app.services.security import dummy_password_check


# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------

@auth_bp.route("/auth/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("adminonline"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "GET":
        return render_template("auth/admin_login.html")

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    admin = Admin.query.filter_by(email=email).first()
    if admin:
        password_ok = admin.check_password(password)
    else:
        dummy_password_check()
        password_ok = False

    if admin and password_ok:
        session.clear()
        session["adminonline"] = admin.id
        return jsonify({"success": True, "redirect_url": url_for("admin.dashboard")})

    return jsonify({"success": False, "message": "Incorrect email or password."}), 401


@auth_bp.route("/auth/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("auth.admin_login"))


# ---------------------------------------------------------------------------
# TEACHER
# ---------------------------------------------------------------------------

@auth_bp.route("/auth/teacher/login", methods=["GET", "POST"])
def teacher_login():
    if session.get("teacheronline"):
        return redirect(url_for("teacher.dashboard"))

    if request.method == "GET":
        return render_template("auth/teacher_login.html")

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    teacher = Teacher.query.filter_by(email=email, is_active=True).first()
    if teacher:
        password_ok = teacher.check_password(password)
    else:
        dummy_password_check()
        password_ok = False

    if teacher and password_ok:
        session.clear()
        session["teacheronline"] = teacher.id
        return jsonify({"success": True, "redirect_url": url_for("teacher.dashboard")})

    return jsonify({"success": False, "message": "Incorrect email or password."}), 401


@auth_bp.route("/auth/teacher/logout")
def teacher_logout():
    session.clear()
    return redirect(url_for("auth.teacher_login"))


# ---------------------------------------------------------------------------
# PARENT / STUDENT PORTAL
# ---------------------------------------------------------------------------

@auth_bp.route("/auth/portal/login", methods=["GET", "POST"])
def portal_login():
    if session.get("studentonline"):
        return redirect(url_for("portal.dashboard"))

    if request.method == "GET":
        return render_template("auth/portal_login.html")

    payload = request.get_json(silent=True) or {}
    admission_number = (payload.get("admission_number") or "").strip()
    password = payload.get("password") or ""

    student = Student.query.filter_by(admission_number=admission_number, is_active=True).first()
    if student:
        password_ok = student.check_password(password)
    else:
        dummy_password_check()
        password_ok = False

    if student and password_ok:
        session.clear()
        session["studentonline"] = student.id
        return jsonify({"success": True, "redirect_url": url_for("portal.dashboard")})

    return jsonify({"success": False, "message": "Incorrect admission number or password."}), 401


@auth_bp.route("/auth/portal/logout")
def portal_logout():
    session.clear()
    return redirect(url_for("auth.portal_login"))

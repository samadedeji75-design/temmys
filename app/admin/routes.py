from flask import render_template, abort, send_file

from app.models import SchoolConfig, Student, Teacher, ClassArm, StudentTermResult
from app.admin import admin_bp
from app.admin.decorators import admin_required


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    config = SchoolConfig.query.first()
    stats = {
        "total_students": Student.query.filter_by(is_active=True).count(),
        "total_teachers": Teacher.query.filter_by(is_active=True).count(),
        "total_classes": ClassArm.query.count(),
        "active_session": config.active_session.name if config and config.active_session else "—",
        "active_term": config.active_term.name if config and config.active_term else "—",
    }
    return render_template(
        "admin/dashboard.html",
        role="admin",
        active_page="dashboard",
        stats=stats,
    )


@admin_bp.route("/sessions-terms")
@admin_required
def sessions_terms():
    return render_template("admin/sessions_terms.html", role="admin", active_page="sessions_terms")


@admin_bp.route("/classes")
@admin_required
def classes_list():
    return render_template("admin/classes_list.html", role="admin", active_page="classes")


@admin_bp.route("/subjects")
@admin_required
def subjects_list():
    return render_template("admin/subjects_list.html", role="admin", active_page="subjects")


@admin_bp.route("/class-subjects")
@admin_required
def class_subjects():
    return render_template("admin/class_subjects.html", role="admin", active_page="class_subjects")


@admin_bp.route("/settings")
@admin_required
def settings():
    return render_template("admin/settings.html", role="admin", active_page="settings")


@admin_bp.route("/grading-scale")
@admin_required
def grading_scale():
    return render_template("admin/grading_scale.html", role="admin", active_page="grading_scale")


@admin_bp.route("/students")
@admin_required
def students_list():
    return render_template("admin/students_list.html", role="admin", active_page="students")


@admin_bp.route("/students/import")
@admin_required
def students_import():
    return render_template("admin/student_import.html", role="admin", active_page="students")


@admin_bp.route("/teachers")
@admin_required
def teachers_list():
    return render_template("admin/teachers_list.html", role="admin", active_page="teachers")


@admin_bp.route("/assignments")
@admin_required
def teacher_assignments():
    return render_template("admin/teacher_assignments.html", role="admin", active_page="assignments")


@admin_bp.route("/classes/<int:arm_id>/students")
@admin_required
def class_roster(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    return render_template(
        "admin/class_roster.html",
        role="admin",
        active_page="classes",
        class_arm_id=arm.id,
        class_arm_name=arm.display_name,
    )


@admin_bp.route("/finalize-term")
@admin_required
def finalize_term():
    return render_template("admin/finalize_term.html", role="admin", active_page="finalize_term")


@admin_bp.route("/results/<int:arm_id>/overview")
@admin_required
def class_result_overview(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    return render_template(
        "admin/class_result_overview.html",
        role="admin", active_page="class_results",
        class_arm_id=arm.id, class_arm_name=arm.display_name,
    )


@admin_bp.route("/results/<int:result_id>")
@admin_required
def student_result(result_id):
    from app.services.results import build_result_context
    result = StudentTermResult.query.get_or_404(result_id)
    if result.status != "finalized":
        abort(404)
    context = build_result_context(result)
    return render_template("admin/student_result.html", role="admin", active_page="class_results", **context)


@admin_bp.route("/results/<int:result_id>/print")
@admin_required
def student_result_print(result_id):
    from app.services.results import build_result_context
    result = StudentTermResult.query.get_or_404(result_id)
    if result.status != "finalized":
        abort(404)
    context = build_result_context(result)
    return render_template("portal/result_print.html", **context)


@admin_bp.route("/results/<int:result_id>/pdf")
@admin_required
def student_result_pdf(result_id):
    from app.services.pdf import build_single_result_pdf, safe_filename

    result = StudentTermResult.query.get_or_404(result_id)
    if result.status != "finalized":
        abort(404)

    pdf_buffer = build_single_result_pdf(result)
    filename = safe_filename(f"{result.student.admission_number}_{result.term.name}_{result.session.name}.pdf")
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


@admin_bp.route("/results/<int:arm_id>/batch-pdf")
@admin_required
def class_result_batch_pdf(arm_id):
    from app.services.pdf import build_batch_result_pdf, safe_filename

    arm = ClassArm.query.get_or_404(arm_id)
    results = (
        StudentTermResult.query.filter_by(status="finalized")
        .join(Student, StudentTermResult.student_id == Student.id)
        .filter(Student.class_arm_id == arm.id, Student.is_active.is_(True))
        .all()
    )
    results.sort(key=lambda r: (r.class_position if r.class_position is not None else 10 ** 9))

    if not results:
        abort(404)

    pdf_buffer = build_batch_result_pdf(results)
    filename = safe_filename(f"{arm.display_name}_batch_results.pdf")
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)
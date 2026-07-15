from flask import render_template, session, abort

from app.models import TeacherSubjectAssignment
from app.teacher import teacher_bp
from app.teacher.decorators import teacher_required


@teacher_bp.route("/dashboard")
@teacher_required
def dashboard():
    return render_template("teacher/dashboard.html", role="teacher", active_page="dashboard")


@teacher_bp.route("/classes/<int:class_arm_id>/subjects/<int:subject_id>/scores")
@teacher_required
def score_entry(class_arm_id, subject_id):
    # Mandatory in the page route too, not just the API — a teacher must
    # never be able to reach this page for a class/subject they aren't
    # assigned to, even by guessing the URL.
    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=session["teacheronline"],
        class_arm_id=class_arm_id,
        subject_id=subject_id,
    ).first()
    if not assignment:
        abort(403)

    return render_template(
        "teacher/score_entry.html",
        role="teacher",
        active_page="score_entry",
        class_arm_id=class_arm_id,
        subject_id=subject_id,
        class_name=assignment.class_arm.display_name,
        subject_name=assignment.subject.name,
    )


@teacher_bp.route("/classes/<int:class_arm_id>/remarks")
@teacher_required
def class_remarks(class_arm_id):
    # Same ownership check as score_entry, but scoped to the class arm only
    # (any subject assignment in this class qualifies — there's no separate
    # "form teacher" concept in this system).
    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=session["teacheronline"],
        class_arm_id=class_arm_id,
    ).first()
    if not assignment:
        abort(403)

    return render_template(
        "teacher/class_remarks.html",
        role="teacher",
        active_page="score_entry",
        class_arm_id=class_arm_id,
        class_name=assignment.class_arm.display_name,
    )
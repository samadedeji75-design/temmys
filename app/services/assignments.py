"""Teacher assignment rules shared by routes.

Holds the remark permission, the primary class sync and the helpers used by
the clear and move flows. Later phases add more helpers here.
"""
from app.models import (
    db,
    ClassArm,
    ClassSubject,
    TeacherSubjectAssignment,
    SECTION_PRIMARY,
    SOURCE_CLASS_TEACHER,
    SOURCE_MANUAL,
)


def teacher_can_write_remarks(teacher_id, class_arm_id):
    """Who may write the class teacher remark for this class.

    If the class has a class teacher, only that teacher may. If it has none,
    fall back to the old rule (any teacher with an assignment in the class) so
    nobody is locked out.
    """
    arm = ClassArm.query.get(class_arm_id)
    if arm is None:
        return False
    if arm.class_teacher_id is not None:
        return teacher_id == arm.class_teacher_id
    return (
        TeacherSubjectAssignment.query.filter_by(
            teacher_id=teacher_id, class_arm_id=arm.id
        ).first()
        is not None
    )


def describe_arm_assignments(arm):
    """Summary of the assignment rows on an arm, grouped by teacher.

    Returns a list of {teacherId, teacherName, subjectCount} sorted by name.
    Used to show the admin what a clear or a cross-section move would remove.
    """
    counts = {}
    for row in TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id).all():
        entry = counts.setdefault(
            row.teacher_id,
            {
                "teacherId": row.teacher_id,
                "teacherName": _teacher_name(row.teacher_id),
                "subjectCount": 0,
            },
        )
        entry["subjectCount"] += 1
    return sorted(counts.values(), key=lambda e: (e["teacherName"] or "").lower())


def clear_arm_assignments(arm, clear_class_teacher=False):
    """Delete every assignment row of the arm. Does not commit.

    A primary arm always loses its class teacher too, otherwise a class
    teacher with no rows would break the primary rule. Scores are untouched.
    Returns the number of rows removed.
    """
    removed = TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id).delete(
        synchronize_session=False
    )
    if clear_class_teacher or arm.class_level.section == SECTION_PRIMARY:
        arm.class_teacher_id = None
    return removed


def _teacher_name(teacher_id):
    from app.models import Teacher

    teacher = Teacher.query.get(teacher_id)
    return teacher.full_name if teacher else None


# ---------------------------------------------------------------------------
# Phase 2: primary class sync
# ---------------------------------------------------------------------------

def sync_primary_arm(arm):
    """Make a primary arm's assignment rows match its class teacher.

    Idempotent and does not commit (the caller commits). Does nothing for
    secondary arms.

    - No class teacher: remove the automatic (class_teacher) rows.
    - Class teacher set: keep exactly one row per subject the class offers,
      owned by the class teacher and marked class_teacher. Any other row in
      the arm (other teachers, rows for subjects no longer offered) is removed.
      A manual row the class teacher already holds for an offered subject is
      kept and re-marked, so no subject is dropped and re-added.
    """
    if (arm.class_level.section or "") != SECTION_PRIMARY:
        return

    rows = TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id).all()

    if arm.class_teacher_id is None:
        for row in rows:
            if row.source == SOURCE_CLASS_TEACHER:
                db.session.delete(row)
        return

    desired = {
        cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id).all()
    }

    kept = set()
    for row in rows:
        if (
            row.teacher_id == arm.class_teacher_id
            and row.subject_id in desired
            and row.subject_id not in kept
        ):
            row.source = SOURCE_CLASS_TEACHER
            kept.add(row.subject_id)
        else:
            db.session.delete(row)

    for subject_id in desired - kept:
        db.session.add(TeacherSubjectAssignment(
            teacher_id=arm.class_teacher_id,
            class_arm_id=arm.id,
            subject_id=subject_id,
            source=SOURCE_CLASS_TEACHER,
        ))


def describe_primary_replacement(arm, new_teacher_id):
    """What sync_primary_arm would remove or re-mark if new_teacher_id became
    the class teacher of this arm. Used for the confirmation step.

    Returns {"replaces": [{teacherId, teacherName, subjectCount}],
             "legacyManualCountForSameTeacher": n}.
    """
    counts = {}
    legacy_manual = 0
    for row in TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id).all():
        if row.teacher_id == new_teacher_id:
            if row.source == SOURCE_MANUAL:
                legacy_manual += 1
            continue
        entry = counts.setdefault(
            row.teacher_id,
            {
                "teacherId": row.teacher_id,
                "teacherName": _teacher_name(row.teacher_id),
                "subjectCount": 0,
            },
        )
        entry["subjectCount"] += 1
    replaces = sorted(counts.values(), key=lambda e: (e["teacherName"] or "").lower())
    return {"replaces": replaces, "legacyManualCountForSameTeacher": legacy_manual}


def convert_arm_automatic_to_manual(arm):
    """Used when a level stops being primary: automatic rows become manual so
    nobody loses access. Does not commit. Returns the number converted."""
    converted = 0
    for row in TeacherSubjectAssignment.query.filter_by(
        class_arm_id=arm.id, source=SOURCE_CLASS_TEACHER
    ).all():
        row.source = SOURCE_MANUAL
        converted += 1
    return converted

"""Teacher assignment rules shared by routes.

Phase 1 only needs the remark permission and a summary helper used by the
clear and move flows. Later phases add the primary sync and other helpers here.
"""
from app.models import ClassArm, TeacherSubjectAssignment


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
    from app.models import SECTION_PRIMARY

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

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


# ---------------------------------------------------------------------------
# Phase 3: class-by-class assignment screen, single-teacher rule, removal checks
# ---------------------------------------------------------------------------

def _holders_by_subject(arm):
    """Assignment rows of an arm grouped by subject id, oldest row first."""
    grouped = {}
    rows = (
        TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id)
        .order_by(TeacherSubjectAssignment.id)
        .all()
    )
    for row in rows:
        grouped.setdefault(row.subject_id, []).append(row)
    return grouped


def _subject_entry(subject, holders):
    """One line of the class assignment list. If legacy data gives a subject
    more than one teacher, the oldest assignment is shown and the others are
    listed in duplicateTeachers so the UI can flag it."""
    first = holders[0] if holders else None
    return {
        "subjectId": subject.id,
        "subjectName": subject.name,
        "teacherId": first.teacher_id if first else None,
        "teacherName": first.teacher.full_name if first else None,
        "teacherActive": first.teacher.is_active if first else None,
        "assignmentId": first.id if first else None,
        "source": first.source if first else None,
        "duplicateTeachers": [h.teacher.full_name for h in holders[1:]],
    }


def class_assignment_entries(arm):
    """One entry per subject the class offers, sorted by subject name."""
    from app.models import Subject

    offered_ids = [cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id).all()]
    subjects = (
        Subject.query.filter(Subject.id.in_(offered_ids)).order_by(Subject.name).all()
        if offered_ids
        else []
    )
    holders = _holders_by_subject(arm)
    return [_subject_entry(subject, holders.get(subject.id, [])) for subject in subjects]


def class_assignment_entry(arm, subject):
    return _subject_entry(subject, _holders_by_subject(arm).get(subject.id, []))


def set_subject_teacher(arm, subject_id, teacher_id):
    """Make teacher_id the only teacher of (arm, subject), or clear the
    subject when teacher_id is None. Does not commit."""
    rows = TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id, subject_id=subject_id).all()

    if teacher_id is None:
        for row in rows:
            db.session.delete(row)
        return

    mine = None
    for row in rows:
        if row.teacher_id == teacher_id and mine is None:
            mine = row
        else:
            db.session.delete(row)

    if mine is None:
        db.session.flush()
        db.session.add(TeacherSubjectAssignment(
            teacher_id=teacher_id, class_arm_id=arm.id, subject_id=subject_id, source=SOURCE_MANUAL
        ))
    else:
        mine.source = SOURCE_MANUAL


def find_conflicts():
    """Every (class, subject) that more than one teacher holds."""
    grouped = {}
    for row in TeacherSubjectAssignment.query.order_by(TeacherSubjectAssignment.id).all():
        grouped.setdefault((row.class_arm_id, row.subject_id), []).append(row)

    conflicts = []
    for (arm_id, subject_id), rows in grouped.items():
        if len(rows) < 2:
            continue
        first = rows[0]
        conflicts.append({
            "classArmId": arm_id,
            "className": first.class_arm.display_name,
            "section": first.class_arm.class_level.section,
            "subjectId": subject_id,
            "subjectName": first.subject.name,
            "teachers": [{"id": r.teacher_id, "name": r.teacher.full_name} for r in rows],
        })
    return sorted(conflicts, key=lambda c: (c["className"], c["subjectName"]))


def find_orphan_rows():
    """Assignment rows for a subject the class does not offer (left behind by
    older versions when a subject was removed from a class)."""
    offered = {(cs.class_arm_id, cs.subject_id) for cs in ClassSubject.query.all()}
    return [
        row
        for row in TeacherSubjectAssignment.query.order_by(TeacherSubjectAssignment.id).all()
        if (row.class_arm_id, row.subject_id) not in offered
    ]


def removal_details(arm, subject_ids):
    """For subjects about to be removed from a class: the teachers who hold
    them and how many scores already exist (any term, students currently in
    the class). Only subjects with teachers or scores are returned."""
    from app.models import Subject, Score, Student

    if not subject_ids:
        return []

    holders = _holders_by_subject(arm)
    student_ids = [s.id for s in Student.query.filter_by(class_arm_id=arm.id).all()]
    details = []
    for subject in Subject.query.filter(Subject.id.in_(list(subject_ids))).order_by(Subject.name).all():
        teachers = [h.teacher.full_name for h in holders.get(subject.id, [])]
        score_count = (
            Score.query.filter(Score.subject_id == subject.id, Score.student_id.in_(student_ids)).count()
            if student_ids
            else 0
        )
        if teachers or score_count:
            details.append({
                "subjectId": subject.id,
                "subjectName": subject.name,
                "teachers": teachers,
                "scoreCount": score_count,
            })
    return details


# ---------------------------------------------------------------------------
# Phase 4: bulk assign, transfer and clear for one teacher
# ---------------------------------------------------------------------------

MAX_BULK_PAIRS = 200


def bulk_assign(teacher, subject_ids, class_arm_ids):
    """Give teacher every (arm, subject) pair of the cross product that is
    allowed. Does not commit. Returns (created_rows, skipped) where skipped is
    a list of {classArmId, subjectId, reason, detail?}.

    Pairs are skipped, never failed, so one bad pair cannot block the rest.
    """
    from app.models import Subject, SECTION_SECONDARY

    arms = {a.id: a for a in ClassArm.query.filter(ClassArm.id.in_(class_arm_ids)).all()}
    subjects = {s.id: s for s in Subject.query.filter(Subject.id.in_(subject_ids)).all()}
    offered = {
        (cs.class_arm_id, cs.subject_id)
        for cs in ClassSubject.query.filter(ClassSubject.class_arm_id.in_(class_arm_ids)).all()
    }
    holders = {}
    for row in (
        TeacherSubjectAssignment.query.filter(
            TeacherSubjectAssignment.class_arm_id.in_(class_arm_ids)
        )
        .order_by(TeacherSubjectAssignment.id)
        .all()
    ):
        holders.setdefault((row.class_arm_id, row.subject_id), []).append(row)

    created = []
    skipped = []
    for arm_id in class_arm_ids:
        for subject_id in subject_ids:
            arm = arms.get(arm_id)
            subject = subjects.get(subject_id)
            entry = {"classArmId": arm_id, "subjectId": subject_id}
            if arm is None:
                skipped.append({**entry, "reason": "arm_not_found"})
                continue
            if subject is None:
                skipped.append({**entry, "reason": "subject_not_found"})
                continue
            if arm.class_level.section != SECTION_SECONDARY:
                skipped.append({**entry, "reason": "primary_arm"})
                continue
            if (arm_id, subject_id) not in offered:
                skipped.append({**entry, "reason": "not_offered"})
                continue
            current = holders.get((arm_id, subject_id), [])
            if any(r.teacher_id == teacher.id for r in current):
                skipped.append({**entry, "reason": "already_assigned"})
                continue
            if current:
                skipped.append({
                    **entry,
                    "reason": "taken",
                    "detail": current[0].teacher.full_name,
                })
                continue
            row = TeacherSubjectAssignment(
                teacher_id=teacher.id,
                class_arm_id=arm_id,
                subject_id=subject_id,
                source=SOURCE_MANUAL,
            )
            db.session.add(row)
            holders[(arm_id, subject_id)] = [row]
            created.append(row)
    db.session.flush()
    return created, skipped


def describe_teacher_workload(teacher):
    """What a clear or transfer would touch: the manual rows the teacher holds
    and the classes they are class teacher of."""
    manual_count = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher.id, source=SOURCE_MANUAL
    ).count()
    arms = ClassArm.query.filter_by(class_teacher_id=teacher.id).all()
    return {
        "manualCount": manual_count,
        "classTeacherOf": sorted(a.display_name for a in arms),
        "classTeacherArms": arms,
    }


def teacher_has_assignments(teacher):
    """True if the teacher holds any assignment row or is a class teacher."""
    if TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id).first() is not None:
        return True
    return ClassArm.query.filter_by(class_teacher_id=teacher.id).first() is not None


def clear_teacher_assignments(teacher):
    """Remove the teacher's manual rows and class teacher roles. Does not
    commit. Primary arms are re-synced so the automatic rows go too (I5).
    Returns (removed_manual_rows, cleared_roles). Scores are untouched."""
    arms = ClassArm.query.filter_by(class_teacher_id=teacher.id).all()
    for arm in arms:
        arm.class_teacher_id = None
    db.session.flush()
    for arm in arms:
        sync_primary_arm(arm)
    removed = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher.id, source=SOURCE_MANUAL
    ).delete(synchronize_session=False)
    db.session.flush()
    return removed, len(arms)


def transfer_teacher_assignments(source, destination):
    """Hand all of source's work to destination. Does not commit.

    1. Class teacher roles move over; primary arms are re-synced so their
       automatic rows are re-owned by the destination.
    2. Remaining manual rows move, unless the destination already holds the
       same (class, subject), in which case the source row is dropped.
    Returns (moved_assignments, moved_roles, skipped_duplicates).
    """
    arms = ClassArm.query.filter_by(class_teacher_id=source.id).all()
    for arm in arms:
        arm.class_teacher_id = destination.id
    db.session.flush()
    for arm in arms:
        sync_primary_arm(arm)
    db.session.flush()

    destination_keys = {
        (r.class_arm_id, r.subject_id)
        for r in TeacherSubjectAssignment.query.filter_by(teacher_id=destination.id).all()
    }
    moved = 0
    skipped = 0
    for row in (
        TeacherSubjectAssignment.query.filter_by(teacher_id=source.id, source=SOURCE_MANUAL)
        .order_by(TeacherSubjectAssignment.id)
        .all()
    ):
        key = (row.class_arm_id, row.subject_id)
        if key in destination_keys:
            db.session.delete(row)
            skipped += 1
        else:
            row.teacher_id = destination.id
            destination_keys.add(key)
            moved += 1
    db.session.flush()
    return moved, len(arms), skipped

"""
app/services/results.py

Shared result-computation logic for the admin Finalize Term / Class Result
Overview / Student Result screens (Phase 5) and the parent portal (Phase 6).
Nothing in this file is route-specific — both app/api/routes.py and (later)
app/portal/routes.py import from here rather than duplicating any of this.
"""

from datetime import datetime

from app.models import (
    db,
    ClassSubject,
    Student,
    Score,
    GradingScale,
    SchoolConfig,
    StudentTermResult,
    Term,
)


# ---------------------------------------------------------------------------
# 3.1 / 3.2 — eligible subjects / students for a class arm
# ---------------------------------------------------------------------------

def get_required_subjects(arm):
    return ClassSubject.query.filter_by(class_arm_id=arm.id).all()


def get_eligible_students(arm):
    return (
        Student.query.filter_by(class_arm_id=arm.id, is_active=True)
        .order_by(Student.full_name)
        .all()
    )


# ---------------------------------------------------------------------------
# 3.3 — per-student completeness
# ---------------------------------------------------------------------------

def is_student_complete(student, required_subjects, term, sess):
    scored_subject_ids = {
        s.subject_id
        for s in Score.query.filter_by(
            student_id=student.id, term_id=term.id, session_id=sess.id
        ).all()
    }
    required_subject_ids = {cs.subject_id for cs in required_subjects}
    return required_subject_ids.issubset(scored_subject_ids)


# ---------------------------------------------------------------------------
# 3.4 — computing one student's totals
# ---------------------------------------------------------------------------

def compute_student_totals(student, required_subjects, term, sess):
    total = 0.0
    for cs in required_subjects:
        score = Score.query.filter_by(
            student_id=student.id,
            subject_id=cs.subject_id,
            term_id=term.id,
            session_id=sess.id,
        ).first()
        total += score.subject_total if score else 0.0  # missing = 0
    average = round(total / len(required_subjects), 1) if required_subjects else 0.0
    grade_row = GradingScale.get_grade(average)
    return round(total, 1), average, (grade_row.grade if grade_row else None)


# ---------------------------------------------------------------------------
# 3.5 — competition ranking ("1224")
# ---------------------------------------------------------------------------

def assign_positions(results):
    """results: list of (student, total) already sorted desc by total."""
    positions = []
    prev_total = None
    prev_position = 0
    for i, (student, total) in enumerate(results, start=1):
        if total != prev_total:
            prev_position = i
        positions.append((student, prev_position))
        prev_total = total
    return positions


# ---------------------------------------------------------------------------
# 3.6 — finalizing a class arm (the write path)
# ---------------------------------------------------------------------------

def _get_finalized_result(student_id, term, sess):
    """Returns the finalized StudentTermResult for this student/term/session,
    or None if that term doesn't exist yet or was never finalized. Used by
    third-term finalization to gather terms 1 and 2 for the session
    cumulative — a missing/unfinalized term is excluded, not treated as 0."""
    if term is None:
        return None
    return StudentTermResult.query.filter_by(
        student_id=student_id, term_id=term.id, session_id=sess.id, status="finalized"
    ).first()


def finalize_class_arm(arm, term, sess):
    """Caller must have already verified required_subjects and students are
    both non-empty. Idempotent / re-runnable — recomputes from current Score
    rows and overwrites any existing StudentTermResult rows.

    Third-term behaviour (term.order == 3): the StudentTermResult row
    written for this term stores the *whole-session* cumulative — first +
    second + third term combined — in cumulative_total/cumulative_average,
    with class_position ranked on that session-wide average, not just this
    term's own figures. Terms 1 and 2 are unaffected: they keep storing
    (and ranking on) that term's own total/average, exactly as before.
    A student missing a finalized term 1 or 2 result has that term simply
    excluded from the session average rather than counted as 0 — the
    average is over whichever terms actually exist.
    """
    required_subjects = get_required_subjects(arm)
    students = get_eligible_students(arm)

    computed = []
    for student in students:
        total, average, grade = compute_student_totals(student, required_subjects, term, sess)
        computed.append((student, total, average, grade))

    if term.order == 3:
        term1 = Term.query.filter_by(session_id=sess.id, order=1).first()
        term2 = Term.query.filter_by(session_id=sess.id, order=2).first()

        session_rows = []  # (student, session_total, session_average, session_grade)
        for student, total, average, grade in computed:
            available_totals = []
            available_averages = []

            prior1 = _get_finalized_result(student.id, term1, sess)
            if prior1:
                available_totals.append(prior1.cumulative_total)
                available_averages.append(prior1.cumulative_average)

            prior2 = _get_finalized_result(student.id, term2, sess)
            if prior2:
                available_totals.append(prior2.cumulative_total)
                available_averages.append(prior2.cumulative_average)

            # This term's own just-computed figures always count.
            available_totals.append(total)
            available_averages.append(average)

            session_total = round(sum(available_totals), 1)
            session_average = round(sum(available_averages) / len(available_averages), 1)
            session_grade_row = GradingScale.get_grade(session_average)
            session_rows.append((
                student, session_total, session_average,
                session_grade_row.grade if session_grade_row else None,
            ))

        session_rows.sort(key=lambda row: row[2], reverse=True)  # rank by session average
        ranked = assign_positions([(row[0], row[2]) for row in session_rows])
        position_by_student = {s.id: pos for s, pos in ranked}

        for student, session_total, session_average, session_grade in session_rows:
            result = StudentTermResult.query.filter_by(
                student_id=student.id, term_id=term.id, session_id=sess.id
            ).first()
            if not result:
                result = StudentTermResult(student_id=student.id, term_id=term.id, session_id=sess.id)
                db.session.add(result)
            result.cumulative_total = session_total
            result.cumulative_average = session_average
            result.overall_grade = session_grade
            result.class_position = position_by_student[student.id]
            result.status = "finalized"
            result.finalized_at = datetime.utcnow()

        db.session.commit()
        return computed

    computed.sort(key=lambda row: row[1], reverse=True)
    ranked = assign_positions([(row[0], row[1]) for row in computed])
    position_by_student = {s.id: pos for s, pos in ranked}

    for student, total, average, grade in computed:
        result = StudentTermResult.query.filter_by(
            student_id=student.id, term_id=term.id, session_id=sess.id
        ).first()
        if not result:
            result = StudentTermResult(student_id=student.id, term_id=term.id, session_id=sess.id)
            db.session.add(result)
        result.cumulative_total = total
        result.cumulative_average = average
        result.overall_grade = grade
        result.class_position = position_by_student[student.id]
        result.status = "finalized"
        result.finalized_at = datetime.utcnow()

    db.session.commit()
    return computed


# ---------------------------------------------------------------------------
# §6 — shared context builder for the result document (admin + portal)
# ---------------------------------------------------------------------------

def build_result_context(result):
    """Returns the Jinja context shared by admin/student_result.html,
    portal/result_view.html, and portal/result_print.html — all three
    render `shared/_result_document.html` off of this exact shape."""
    student = result.student
    class_arm = student.class_arm
    term = result.term
    sess = result.session

    config = SchoolConfig.query.first()
    ca_max = config.ca_max_score if config else 40
    exam_max = config.exam_max_score if config else 60

    class_size = Student.query.filter_by(class_arm_id=class_arm.id, is_active=True).count()

    required_subjects = get_required_subjects(class_arm)
    # Sort by subject name for stable, human-friendly ordering.
    required_subjects = sorted(required_subjects, key=lambda cs: cs.subject.name)

    subject_rows = []
    for cs in required_subjects:
        score = Score.query.filter_by(
            student_id=student.id,
            subject_id=cs.subject_id,
            term_id=term.id,
            session_id=sess.id,
        ).first()
        if score:
            subject_rows.append({
                "subject_name": cs.subject.name,
                "ca1": score.ca1,
                "ca2": score.ca2,
                "ca3": score.ca3,
                "ca_total": score.ca_total,
                "exam_score": score.exam_score,
                "subject_total": score.subject_total,
                "grade": score.subject_grade,
                "remark": score.subject_remark,
            })
        else:
            subject_rows.append({
                "subject_name": cs.subject.name,
                "ca1": None,
                "ca2": None,
                "ca3": None,
                "ca_total": None,
                "exam_score": None,
                "subject_total": None,
                "grade": None,
                "remark": None,
            })

    return {
        "student": student,
        "class_arm": class_arm,
        "term": term,
        "session": sess,
        "result": result,
        "class_size": class_size,
        "subject_rows": subject_rows,
        "ca_max": ca_max,
        "exam_max": exam_max,
    }

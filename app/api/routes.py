import csv
import io
import secrets
from datetime import datetime

import os
import uuid
from flask import jsonify, request, current_app, session
from werkzeug.utils import secure_filename

from app.models import (
    db,
    Session,
    Term,
    ClassLevel,
    ClassArm,
    Subject,
    ClassSubject,
    GradingScale,
    SchoolConfig,
    Student,
    Teacher,
    TeacherSubjectAssignment,
    Score,
    StudentTermResult,
)
from app.api import api_bp
from app.api.decorators import api_admin_required, api_teacher_required, api_portal_required
from app.services.security import encrypt_password, decrypt_password
from app.services.results import (
    get_required_subjects,
    get_eligible_students,
    is_student_complete,
    finalize_class_arm,
)

ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg"}  # no SVG — can carry embedded <script>, stored-XSS risk if the file URL is opened directly
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2MB — generous for a logo, keeps page load fast


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Serialization helpers — keep JSON shape here, not scattered across routes
# ---------------------------------------------------------------------------

def serialize_term(term):
    config = SchoolConfig.query.first()
    is_active = bool(config and config.active_term_id == term.id)
    return {
        "id": term.id,
        "sessionId": term.session_id,
        "name": term.name,
        "order": term.order,
        "active": is_active,
        "locked": term.is_locked,
    }


def serialize_session(session_obj):
    return {
        "id": session_obj.id,
        "name": session_obj.name,
        "active": session_obj.is_active,
        "terms": [serialize_term(t) for t in sorted(session_obj.terms, key=lambda t: t.order)],
    }


def serialize_arm(arm):
    return {
        "id": arm.id,
        "levelId": arm.class_level_id,
        "name": arm.name,
        "studentCount": len(arm.students),
    }


def serialize_level(level):
    return {"id": level.id, "name": level.name, "order": level.order}


def serialize_subject(subject):
    return {"id": subject.id, "name": subject.name, "code": subject.code}


def serialize_student(student):
    return {
        "id": student.id,
        "admissionNumber": student.admission_number,
        "fullName": student.full_name,
        "gender": student.gender,
        "dateOfBirth": student.date_of_birth.isoformat() if student.date_of_birth else None,
        "guardianName": student.guardian_name,
        "guardianPhone": student.guardian_phone,
        "guardianEmail": student.guardian_email,
        "classArmId": student.class_arm_id,
        "className": student.class_arm.display_name if student.class_arm else None,
        "isActive": student.is_active,
    }


def serialize_teacher(teacher):
    return {
        "id": teacher.id,
        "fullName": teacher.full_name,
        "email": teacher.email,
        "emailIsPlaceholder": teacher.email.endswith("@placeholder.local"),
        "isActive": teacher.is_active,
        "assignmentCount": len(teacher.assignments),
    }


def serialize_assignment(assignment):
    return {
        "id": assignment.id,
        "classArmId": assignment.class_arm_id,
        "className": assignment.class_arm.display_name if assignment.class_arm else None,
        "subjectId": assignment.subject_id,
        "subjectName": assignment.subject.name if assignment.subject else None,
    }


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------------------
# SESSIONS & TERMS
# ---------------------------------------------------------------------------

@api_bp.route("/sessions", methods=["GET"])
@api_admin_required
def list_sessions():
    sessions = Session.query.order_by(Session.name.desc()).all()
    return jsonify({"success": True, "sessions": [serialize_session(s) for s in sessions]})


@api_bp.route("/sessions", methods=["POST"])
@api_admin_required
def create_session():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Session name is required."}), 400
    if Session.query.filter_by(name=name).first():
        return jsonify({"success": False, "message": "That session already exists."}), 409

    session_obj = Session(name=name, is_active=False)
    db.session.add(session_obj)
    db.session.commit()
    return jsonify({"success": True, "session": serialize_session(session_obj)}), 201


@api_bp.route("/sessions/<int:session_id>/activate", methods=["PUT"])
@api_admin_required
def activate_session(session_id):
    session_obj = Session.query.get_or_404(session_id)
    Session.query.update({Session.is_active: False})
    session_obj.is_active = True
    db.session.commit()
    return jsonify({"success": True, "session": serialize_session(session_obj)})


@api_bp.route("/terms", methods=["POST"])
@api_admin_required
def create_term():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("sessionId")
    name = (payload.get("name") or "").strip()
    order = payload.get("order")

    if not session_id or not name:
        return jsonify({"success": False, "message": "Session and term name are required."}), 400

    try:
        order = int(order)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Term order (1st/2nd/3rd) is required."}), 400
    if order not in (1, 2, 3):
        return jsonify({"success": False, "message": "Term order must be 1, 2, or 3."}), 400

    session_obj = Session.query.get(session_id)
    if not session_obj:
        return jsonify({"success": False, "message": "Session not found."}), 404

    if Term.query.filter_by(session_id=session_id, name=name).first():
        return jsonify({"success": False, "message": "That term already exists for this session."}), 409
    if Term.query.filter_by(session_id=session_id, order=order).first():
        return jsonify({"success": False, "message": "This session already has a term with that order (1st/2nd/3rd)."}), 409

    term = Term(name=name, session_id=session_id, is_locked=True, order=order)
    db.session.add(term)
    db.session.commit()
    return jsonify({"success": True, "term": serialize_term(term)}), 201


@api_bp.route("/terms/<int:term_id>/activate", methods=["PUT"])
@api_admin_required
def activate_term(term_id):
    term = Term.query.get_or_404(term_id)
    config = SchoolConfig.query.first()
    if not config:
        return jsonify({"success": False, "message": "School configuration not set up yet."}), 400
    config.active_term_id = term.id
    config.active_session_id = term.session_id
    db.session.commit()
    return jsonify({"success": True, "term": serialize_term(term)})


@api_bp.route("/terms/<int:term_id>/lock", methods=["PUT"])
@api_admin_required
def lock_term(term_id):
    term = Term.query.get_or_404(term_id)
    term.is_locked = True
    db.session.commit()
    return jsonify({"success": True, "term": serialize_term(term)})


@api_bp.route("/terms/<int:term_id>/unlock", methods=["PUT"])
@api_admin_required
def unlock_term(term_id):
    term = Term.query.get_or_404(term_id)
    term.is_locked = False
    db.session.commit()
    return jsonify({"success": True, "term": serialize_term(term)})


# ---------------------------------------------------------------------------
# CLASSES (levels + arms)
# ---------------------------------------------------------------------------

@api_bp.route("/classes", methods=["GET"])
@api_admin_required
def list_classes():
    levels = ClassLevel.query.order_by(ClassLevel.order).all()
    arms = ClassArm.query.all()
    return jsonify({
        "success": True,
        "levels": [serialize_level(lvl) for lvl in levels],
        "arms": [serialize_arm(arm) for arm in arms],
    })


@api_bp.route("/classes/levels", methods=["POST"])
@api_admin_required
def create_class_level():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Level name is required."}), 400
    if ClassLevel.query.filter_by(name=name).first():
        return jsonify({"success": False, "message": "That class level already exists."}), 409

    max_order = db.session.query(db.func.max(ClassLevel.order)).scalar() or 0
    level = ClassLevel(name=name, order=max_order + 1)
    db.session.add(level)
    db.session.commit()
    return jsonify({"success": True, "level": serialize_level(level)}), 201


@api_bp.route("/classes/arms", methods=["POST"])
@api_admin_required
def create_class_arm():
    payload = request.get_json(silent=True) or {}
    level_id = payload.get("levelId")
    name = (payload.get("name") or "").strip()

    if not level_id or not name:
        return jsonify({"success": False, "message": "Level and arm name are required."}), 400
    if not ClassLevel.query.get(level_id):
        return jsonify({"success": False, "message": "Class level not found."}), 404
    if ClassArm.query.filter_by(class_level_id=level_id, name=name).first():
        return jsonify({"success": False, "message": "That arm already exists for this level."}), 409

    arm = ClassArm(name=name, class_level_id=level_id)
    db.session.add(arm)
    db.session.commit()
    return jsonify({"success": True, "arm": serialize_arm(arm)}), 201


@api_bp.route("/classes/arms/<int:arm_id>", methods=["PUT"])
@api_admin_required
def update_class_arm(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    payload = request.get_json(silent=True) or {}
    level_id = payload.get("levelId", arm.class_level_id)
    name = (payload.get("name") or arm.name).strip()

    if not ClassLevel.query.get(level_id):
        return jsonify({"success": False, "message": "Class level not found."}), 404

    arm.class_level_id = level_id
    arm.name = name
    db.session.commit()
    return jsonify({"success": True, "arm": serialize_arm(arm)})


@api_bp.route("/classes/arms/<int:arm_id>", methods=["DELETE"])
@api_admin_required
def delete_class_arm(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    if arm.students:
        return jsonify({
            "success": False,
            "message": f"Can't delete '{arm.display_name}' — it still has students assigned.",
        }), 409
    db.session.delete(arm)
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# CLASS <-> SUBJECT ASSIGNMENT
# ---------------------------------------------------------------------------

@api_bp.route("/classes/<int:arm_id>/subjects", methods=["GET"])
@api_admin_required
def get_class_subjects(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    subject_ids = [cs.subject_id for cs in arm.class_subjects]
    return jsonify({"success": True, "armId": arm.id, "subjectIds": subject_ids})


@api_bp.route("/classes/<int:arm_id>/subjects", methods=["PUT"])
@api_admin_required
def set_class_subjects(arm_id):
    arm = ClassArm.query.get_or_404(arm_id)
    payload = request.get_json(silent=True) or {}
    selected_ids = set(payload.get("subjectIds") or [])

    current_ids = {cs.subject_id for cs in arm.class_subjects}

    for cs in list(arm.class_subjects):
        if cs.subject_id not in selected_ids:
            db.session.delete(cs)

    for sid in selected_ids - current_ids:
        if Subject.query.get(sid):
            db.session.add(ClassSubject(class_arm_id=arm.id, subject_id=sid))

    db.session.commit()
    return jsonify({"success": True, "armId": arm.id, "subjectIds": list(selected_ids)})


# ---------------------------------------------------------------------------
# SUBJECTS
# ---------------------------------------------------------------------------

@api_bp.route("/subjects", methods=["GET"])
@api_admin_required
def list_subjects():
    subjects = Subject.query.order_by(Subject.name).all()
    return jsonify({"success": True, "subjects": [serialize_subject(s) for s in subjects]})


@api_bp.route("/subjects", methods=["POST"])
@api_admin_required
def create_subject():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip() or None

    if not name:
        return jsonify({"success": False, "message": "Subject name is required."}), 400
    if Subject.query.filter_by(name=name).first():
        return jsonify({"success": False, "message": "That subject already exists."}), 409

    subject = Subject(name=name, code=code)
    db.session.add(subject)
    db.session.commit()
    return jsonify({"success": True, "subject": serialize_subject(subject)}), 201


@api_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
@api_admin_required
def update_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or subject.name).strip()
    code = (payload.get("code") or subject.code or "").strip() or None

    subject.name = name
    subject.code = code
    db.session.commit()
    return jsonify({"success": True, "subject": serialize_subject(subject)})


@api_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@api_admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if ClassSubject.query.filter_by(subject_id=subject.id).first():
        return jsonify({
            "success": False,
            "message": f"Can't delete '{subject.name}' — it's assigned to one or more classes.",
        }), 409
    db.session.delete(subject)
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# GRADING SCALE (+ CA/Exam max config, stored on SchoolConfig)
# ---------------------------------------------------------------------------

@api_bp.route("/grading-scale", methods=["GET"])
@api_admin_required
def get_grading_scale():
    config = SchoolConfig.query.first()
    bands = GradingScale.query.order_by(GradingScale.min_score.desc()).all()
    return jsonify({
        "success": True,
        "caMax": config.ca_max_score if config else 40,
        "examMax": config.exam_max_score if config else 60,
        "rows": [
            {"id": b.id, "min": b.min_score, "max": b.max_score, "grade": b.grade, "remark": b.remark}
            for b in bands
        ],
    })


@api_bp.route("/grading-scale", methods=["POST"])
@api_admin_required
def save_grading_scale():
    payload = request.get_json(silent=True) or {}
    ca_max = payload.get("caMax")
    exam_max = payload.get("examMax")
    rows = payload.get("rows") or []

    seen = []
    for row in rows:
        if row.get("min") is None or row.get("max") is None or not row.get("grade"):
            return jsonify({"success": False, "message": "Every row needs a min, max, and grade."}), 400
        if row["min"] > row["max"]:
            return jsonify({"success": False, "message": f"Row '{row['grade']}': min is greater than max."}), 400
        seen.append(row)

    seen.sort(key=lambda r: r["min"])
    for a, b in zip(seen, seen[1:]):
        if a["max"] >= b["min"]:
            return jsonify({
                "success": False,
                "message": f"Overlap between '{a['grade']}' and '{b['grade']}'.",
            }), 400

    config = SchoolConfig.query.first()
    if not config:
        config = SchoolConfig(school_name="Unnamed School")
        db.session.add(config)
    if ca_max is not None:
        config.ca_max_score = ca_max
    if exam_max is not None:
        config.exam_max_score = exam_max

    # Replace the grading scale wholesale — simplest way to handle
    # add/edit/delete rows all coming from one client-side table
    GradingScale.query.delete()
    for row in rows:
        db.session.add(GradingScale(
            min_score=row["min"],
            max_score=row["max"],
            grade=row["grade"].strip(),
            remark=(row.get("remark") or "").strip() or None,
        ))

    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# SCHOOL SETTINGS (branding/contact info — what makes this app resellable
# to a different school without touching any HTML/code)
# ---------------------------------------------------------------------------

def _allowed_logo_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


@api_bp.route("/settings", methods=["GET"])
@api_admin_required
def get_settings():
    config = SchoolConfig.query.first()
    if not config:
        return jsonify({
            "success": True,
            "schoolName": "",
            "address": "",
            "phone": "",
            "email": "",
            "motto": "",
            "logoPath": None,
        })
    return jsonify({
        "success": True,
        "schoolName": config.school_name,
        "address": config.address or "",
        "phone": config.phone or "",
        "email": config.email or "",
        "motto": config.motto or "",
        "logoPath": config.logo_path,
    })


@api_bp.route("/settings", methods=["POST"])
@api_admin_required
def save_settings():
    """
    Accepts multipart/form-data (not JSON) because logo upload requires it.
    Text fields arrive via request.form, the logo (if provided) via
    request.files. The frontend must NOT use window.apiRequest() for this
    endpoint — that helper hardcodes JSON content-type. Use a raw $.ajax
    call with FormData, processData:false, contentType:false, and still
    attach the X-CSRFToken header manually.
    """
    school_name = (request.form.get("schoolName") or "").strip()
    address = (request.form.get("address") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    email = (request.form.get("email") or "").strip()
    motto = (request.form.get("motto") or "").strip()

    if not school_name:
        return jsonify({"success": False, "message": "School name is required."}), 400

    config = SchoolConfig.query.first()
    if not config:
        config = SchoolConfig(school_name=school_name)
        db.session.add(config)

    config.school_name = school_name
    config.address = address or None
    config.phone = phone or None
    config.email = email or None
    config.motto = motto or None

    logo_file = request.files.get("logo")
    if logo_file and logo_file.filename:
        if not _allowed_logo_file(logo_file.filename):
            return jsonify({
                "success": False,
                "message": "Logo must be a PNG or JPG file.",
            }), 400

        logo_file.seek(0, os.SEEK_END)
        size = logo_file.tell()
        logo_file.seek(0)
        if size > MAX_LOGO_SIZE_BYTES:
            return jsonify({"success": False, "message": "Logo must be under 2MB."}), 400

        ext = logo_file.filename.rsplit(".", 1)[1].lower()
        safe_name = f"{uuid.uuid4().hex}.{ext}"
        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "logos")
        os.makedirs(upload_dir, exist_ok=True)
        logo_file.save(os.path.join(upload_dir, secure_filename(safe_name)))

        config.logo_path = f"/static/uploads/logos/{safe_name}"

    db.session.commit()
    return jsonify({
        "success": True,
        "schoolName": config.school_name,
        "address": config.address or "",
        "phone": config.phone or "",
        "email": config.email or "",
        "motto": config.motto or "",
        "logoPath": config.logo_path,
    })


# ---------------------------------------------------------------------------
# STUDENTS
# ---------------------------------------------------------------------------

def _generate_admission_number(exclude=None):
    """Unique admission number in STU/<year>/<seq> form, used whenever the
    admin (or a CSV row) doesn't supply one. `exclude` lets a caller pass in
    admission numbers already claimed earlier in the same request (e.g. an
    in-progress CSV import batch) that aren't committed to the DB yet."""
    exclude = {e.lower() for e in (exclude or set())}
    year = datetime.utcnow().year
    prefix = f"STU/{year}/"
    existing = {
        a.lower() for (a,) in db.session.query(Student.admission_number)
        .filter(Student.admission_number.ilike(f"{prefix}%"))
        .all()
    }
    existing |= exclude
    seq = 1
    while True:
        candidate = f"{prefix}{seq:04d}"
        if candidate.lower() not in existing:
            return candidate
        seq += 1


@api_bp.route("/students", methods=["GET"])
@api_admin_required
def list_students():
    query = Student.query
    class_arm_id = request.args.get("classArmId")
    if class_arm_id:
        query = query.filter_by(class_arm_id=class_arm_id)
    students = query.order_by(Student.full_name).all()
    return jsonify({"success": True, "students": [serialize_student(s) for s in students]})


@api_bp.route("/students", methods=["POST"])
@api_admin_required
def create_student():
    payload = request.get_json(silent=True) or {}
    admission_number = (payload.get("admissionNumber") or "").strip()
    full_name = (payload.get("fullName") or "").strip()
    class_arm_id = payload.get("classArmId")

    if not full_name or not class_arm_id:
        return jsonify({
            "success": False,
            "message": "Full name and class are required.",
        }), 400

    if admission_number:
        if Student.query.filter_by(admission_number=admission_number).first():
            return jsonify({"success": False, "message": "That admission number is already in use."}), 409
    else:
        admission_number = _generate_admission_number()

    class_arm = ClassArm.query.get(class_arm_id)
    if not class_arm:
        return jsonify({"success": False, "message": "Class not found."}), 404

    student = Student(
        admission_number=admission_number,
        full_name=full_name,
        gender=(payload.get("gender") or None),
        date_of_birth=_parse_date(payload.get("dateOfBirth")),
        guardian_name=(payload.get("guardianName") or None),
        guardian_phone=(payload.get("guardianPhone") or None),
        guardian_email=(payload.get("guardianEmail") or None),
        class_arm_id=class_arm.id,
    )

    raw_password = payload.get("password") or secrets.token_urlsafe(8)
    student.set_password(raw_password)
    student.password_encrypted = encrypt_password(raw_password)

    db.session.add(student)
    db.session.commit()

    response = serialize_student(student)
    response["generatedPassword"] = raw_password
    return jsonify({"success": True, "student": response}), 201


@api_bp.route("/students/<int:student_id>", methods=["PUT"])
@api_admin_required
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    payload = request.get_json(silent=True) or {}

    full_name = (payload.get("fullName") or student.full_name).strip()
    class_arm_id = payload.get("classArmId", student.class_arm_id)

    if not full_name or not class_arm_id:
        return jsonify({"success": False, "message": "Full name and class are required."}), 400

    class_arm = ClassArm.query.get(class_arm_id)
    if not class_arm:
        return jsonify({"success": False, "message": "Class not found."}), 404

    student.full_name = full_name
    student.class_arm_id = class_arm.id
    student.gender = payload.get("gender", student.gender)
    if "dateOfBirth" in payload:
        student.date_of_birth = _parse_date(payload.get("dateOfBirth"))
    student.guardian_name = payload.get("guardianName", student.guardian_name)
    student.guardian_phone = payload.get("guardianPhone", student.guardian_phone)
    student.guardian_email = payload.get("guardianEmail", student.guardian_email)

    db.session.commit()
    return jsonify({"success": True, "student": serialize_student(student)})


@api_bp.route("/students/<int:student_id>/deactivate", methods=["POST"])
@api_admin_required
def deactivate_student(student_id):
    student = Student.query.get_or_404(student_id)
    payload = request.get_json(silent=True) or {}
    # Allow toggling back to active (reactivate) from the same endpoint the
    # UI calls, since students are never hard-deleted.
    if "isActive" in payload:
        student.is_active = bool(payload["isActive"])
    else:
        student.is_active = False
    db.session.commit()
    return jsonify({"success": True, "student": serialize_student(student)})


@api_bp.route("/students/<int:student_id>/reset-password", methods=["POST"])
@api_admin_required
def reset_student_password(student_id):
    student = Student.query.get_or_404(student_id)
    new_password = secrets.token_urlsafe(8)
    student.set_password(new_password)
    student.password_encrypted = encrypt_password(new_password)
    db.session.commit()
    return jsonify({"success": True, "generatedPassword": new_password})


@api_bp.route("/students/<int:student_id>/password", methods=["GET"])
@api_admin_required
def get_student_password(student_id):
    student = Student.query.get_or_404(student_id)
    password = decrypt_password(student.password_encrypted)
    return jsonify({"success": True, "password": password})  # password is null if unavailable


@api_bp.route("/students/<int:student_id>/password", methods=["PUT"])
@api_admin_required
def set_student_password(student_id):
    student = Student.query.get_or_404(student_id)
    payload = request.get_json(silent=True) or {}
    new_password = (payload.get("password") or "").strip()
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400
    student.set_password(new_password)
    student.password_encrypted = encrypt_password(new_password)
    db.session.commit()
    return jsonify({"success": True})


# full_name and class_arm are the only truly required columns — admission
# number and the rest can be left blank and are auto-generated/omitted per
# row (see import loop below), matching the single-add endpoint's behavior.
REQUIRED_IMPORT_COLUMNS = ["full_name", "class_arm"]


@api_bp.route("/students/import", methods=["POST"])
@api_admin_required
def import_students():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"success": False, "message": "No file uploaded."}), 400
    if not upload.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "message": "Please upload a .csv file."}), 400

    try:
        raw = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"success": False, "message": "Could not read the file as UTF-8 text."}), 400

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        return jsonify({"success": False, "message": "The CSV file has no data rows."}), 400

    header_map = {h.strip().lower(): h for h in reader.fieldnames}
    missing = [c for c in REQUIRED_IMPORT_COLUMNS if c not in header_map]
    if missing:
        return jsonify({
            "success": False,
            "message": f"CSV is missing required column(s): {', '.join(missing)}",
        }), 400

    arms_by_display_name = {arm.display_name.lower(): arm for arm in ClassArm.query.all()}
    existing_admission_numbers = {
        a.lower() for (a,) in db.session.query(Student.admission_number).all()
    }

    imported = 0
    skipped = []
    seen_in_file = set()

    for row_number, row in enumerate(reader, start=2):
        def col(name):
            key = header_map.get(name)
            if not key:
                return ""
            return (row.get(key) or "").strip()

        admission_number = col("admission_number")
        full_name = col("full_name")
        class_arm_name = col("class_arm")

        if not full_name or not class_arm_name:
            skipped.append({"row": row_number, "reason": "Missing required field (full_name or class_arm)."})
            continue

        if admission_number:
            if admission_number.lower() in existing_admission_numbers or admission_number.lower() in seen_in_file:
                skipped.append({
                    "row": row_number,
                    "reason": f"Duplicate admission number {admission_number}",
                })
                continue
        else:
            admission_number = _generate_admission_number(seen_in_file)

        arm = arms_by_display_name.get(class_arm_name.lower())
        if not arm:
            skipped.append({
                "row": row_number,
                "reason": f"Class arm '{class_arm_name}' not found",
            })
            continue

        student = Student(
            admission_number=admission_number,
            full_name=full_name,
            gender=col("gender") or None,
            date_of_birth=_parse_date(col("date_of_birth")),
            guardian_name=col("guardian_name") or None,
            guardian_phone=col("guardian_phone") or None,
            guardian_email=col("guardian_email") or None,
            class_arm_id=arm.id,
        )
        raw_password = secrets.token_urlsafe(8)
        student.set_password(raw_password)
        student.password_encrypted = encrypt_password(raw_password)
        db.session.add(student)

        seen_in_file.add(admission_number.lower())
        imported += 1

    db.session.commit()
    return jsonify({"success": True, "imported": imported, "skipped": skipped})


# ---------------------------------------------------------------------------
# TEACHERS
# ---------------------------------------------------------------------------

@api_bp.route("/teachers", methods=["GET"])
@api_admin_required
def list_teachers():
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return jsonify({"success": True, "teachers": [serialize_teacher(t) for t in teachers]})


def _generate_placeholder_email():
    """Unique, obviously-not-real placeholder used when an admin adds a
    teacher with just a name. Must be replaced with a real email later —
    a teacher can't practically receive their login credentials until
    then, but the account exists and a password is already set so nothing
    blocks completing the rest of their profile."""
    while True:
        candidate = f"pending.{secrets.token_hex(4)}@placeholder.local"
        if not Teacher.query.filter_by(email=candidate).first():
            return candidate


@api_bp.route("/teachers", methods=["POST"])
@api_admin_required
def create_teacher():
    payload = request.get_json(silent=True) or {}
    full_name = (payload.get("fullName") or "").strip()
    email = (payload.get("email") or "").strip().lower()

    if not full_name:
        return jsonify({"success": False, "message": "Full name is required."}), 400

    email_auto_generated = not bool(email)
    if email:
        if Teacher.query.filter_by(email=email).first():
            return jsonify({"success": False, "message": "That email is already in use."}), 409
    else:
        email = _generate_placeholder_email()

    teacher = Teacher(full_name=full_name, email=email)
    raw_password = payload.get("password") or secrets.token_urlsafe(8)
    teacher.set_password(raw_password)
    teacher.password_encrypted = encrypt_password(raw_password)

    db.session.add(teacher)
    db.session.commit()

    response = serialize_teacher(teacher)
    response["generatedPassword"] = raw_password
    response["emailAutoGenerated"] = email_auto_generated
    return jsonify({"success": True, "teacher": response}), 201


@api_bp.route("/teachers/<int:teacher_id>", methods=["PUT"])
@api_admin_required
def update_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    payload = request.get_json(silent=True) or {}

    full_name = (payload.get("fullName") or teacher.full_name).strip()
    email = (payload.get("email") or teacher.email).strip().lower()

    if not full_name or not email:
        return jsonify({"success": False, "message": "Full name and email are required."}), 400

    existing = Teacher.query.filter_by(email=email).first()
    if existing and existing.id != teacher.id:
        return jsonify({"success": False, "message": "That email is already in use."}), 409

    teacher.full_name = full_name
    teacher.email = email
    db.session.commit()
    return jsonify({"success": True, "teacher": serialize_teacher(teacher)})


@api_bp.route("/teachers/<int:teacher_id>/deactivate", methods=["POST"])
@api_admin_required
def deactivate_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    payload = request.get_json(silent=True) or {}
    if "isActive" in payload:
        teacher.is_active = bool(payload["isActive"])
    else:
        teacher.is_active = False
    db.session.commit()
    return jsonify({"success": True, "teacher": serialize_teacher(teacher)})


@api_bp.route("/teachers/<int:teacher_id>/reset-password", methods=["POST"])
@api_admin_required
def reset_teacher_password(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    new_password = secrets.token_urlsafe(8)
    teacher.set_password(new_password)
    teacher.password_encrypted = encrypt_password(new_password)
    db.session.commit()
    return jsonify({"success": True, "generatedPassword": new_password})


@api_bp.route("/teachers/<int:teacher_id>/password", methods=["GET"])
@api_admin_required
def get_teacher_password(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    password = decrypt_password(teacher.password_encrypted)
    return jsonify({"success": True, "password": password})  # password is null if unavailable


@api_bp.route("/teachers/<int:teacher_id>/password", methods=["PUT"])
@api_admin_required
def set_teacher_password(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    payload = request.get_json(silent=True) or {}
    new_password = (payload.get("password") or "").strip()
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400
    teacher.set_password(new_password)
    teacher.password_encrypted = encrypt_password(new_password)
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# TEACHER <-> CLASS/SUBJECT ASSIGNMENTS
# ---------------------------------------------------------------------------

@api_bp.route("/teachers/<int:teacher_id>/assignments", methods=["GET"])
@api_admin_required
def list_teacher_assignments(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    assignments = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id).all()
    return jsonify({"success": True, "assignments": [serialize_assignment(a) for a in assignments]})


@api_bp.route("/teachers/<int:teacher_id>/assignments", methods=["POST"])
@api_admin_required
def create_teacher_assignment(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    payload = request.get_json(silent=True) or {}
    class_arm_id = payload.get("classArmId")
    subject_id = payload.get("subjectId")

    if not class_arm_id or not subject_id:
        return jsonify({"success": False, "message": "Class and subject are required."}), 400

    class_arm = ClassArm.query.get(class_arm_id)
    if not class_arm:
        return jsonify({"success": False, "message": "Class not found."}), 404
    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"success": False, "message": "Subject not found."}), 404

    offered = ClassSubject.query.filter_by(class_arm_id=class_arm.id, subject_id=subject.id).first()
    if not offered:
        return jsonify({
            "success": False,
            "message": "That subject isn't offered by this class.",
        }), 400

    duplicate = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher.id, class_arm_id=class_arm.id, subject_id=subject.id
    ).first()
    if duplicate:
        return jsonify({"success": False, "message": "This assignment already exists."}), 409

    assignment = TeacherSubjectAssignment(
        teacher_id=teacher.id, class_arm_id=class_arm.id, subject_id=subject.id
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"success": True, "assignment": serialize_assignment(assignment)}), 201


@api_bp.route("/teacher-assignments/<int:assignment_id>", methods=["DELETE"])
@api_admin_required
def delete_teacher_assignment(assignment_id):
    assignment = TeacherSubjectAssignment.query.get_or_404(assignment_id)
    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# TEACHER PORTAL — dashboard + score entry
#
# CRITICAL: every route below scopes to session["teacheronline"] and verifies
# a matching TeacherSubjectAssignment row before touching any Score data.
# Never trust a classArmId/subjectId from the request without that check.
# ---------------------------------------------------------------------------

def _get_active_term():
    """Returns (session_obj, term) for the school's currently active
    term/session, or (None, None) if not configured yet."""
    config = SchoolConfig.query.first()
    if not config or not config.active_term_id or not config.active_session_id:
        return None, None
    return config.active_session, config.active_term


def _serialize_student_score(student, score, ca_max, exam_max):
    if score is None:
        return {
            "studentId": student.id,
            "admissionNumber": student.admission_number,
            "fullName": student.full_name,
            "ca1": None, "ca2": None, "ca3": None, "examScore": None,
            "caTotal": None, "subjectTotal": None, "grade": None,
        }
    return {
        "studentId": student.id,
        "admissionNumber": student.admission_number,
        "fullName": student.full_name,
        "ca1": score.ca1, "ca2": score.ca2, "ca3": score.ca3, "examScore": score.exam_score,
        "caTotal": score.ca_total, "subjectTotal": score.subject_total, "grade": score.subject_grade,
    }


@api_bp.route("/teacher/my-assignments", methods=["GET"])
@api_teacher_required
def teacher_my_assignments():
    teacher_id = session["teacheronline"]
    active_session, active_term = _get_active_term()

    assignments = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher_id).all()

    result = []
    for a in assignments:
        students_total = Student.query.filter_by(class_arm_id=a.class_arm_id, is_active=True).count()

        entered = 0
        if active_term and active_session:
            # A row "counts as entered" once the teacher has recorded an exam
            # score for the student — CA-only entries are treated as
            # still-in-progress, since the exam score is normally the last
            # piece entered and the best signal a student's row is complete.
            entered = (
                db.session.query(Score)
                .join(Student, Score.student_id == Student.id)
                .filter(
                    Score.subject_id == a.subject_id,
                    Score.term_id == active_term.id,
                    Score.session_id == active_session.id,
                    Student.class_arm_id == a.class_arm_id,
                    Student.is_active.is_(True),
                    Score.exam_score.isnot(None),
                    Score.exam_score > 0,
                )
                .count()
            )

        result.append({
            "classArmId": a.class_arm_id,
            "className": a.class_arm.display_name if a.class_arm else None,
            "subjectId": a.subject_id,
            "subjectName": a.subject.name if a.subject else None,
            "studentsTotal": students_total,
            "studentsWithScoresEntered": entered,
        })

    return jsonify({"success": True, "assignments": result})


@api_bp.route("/teacher/scores", methods=["GET"])
@api_teacher_required
def get_teacher_scores():
    teacher_id = session["teacheronline"]
    class_arm_id = request.args.get("classArmId", type=int)
    subject_id = request.args.get("subjectId", type=int)

    if not class_arm_id or not subject_id:
        return jsonify({"success": False, "message": "classArmId and subjectId are required."}), 400

    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher_id, class_arm_id=class_arm_id, subject_id=subject_id
    ).first()
    if not assignment:
        return jsonify({"success": False, "message": "You are not assigned to this class and subject."}), 403

    config = SchoolConfig.query.first()
    active_session, active_term = _get_active_term()

    ca_max = config.ca_max_score if config else 40
    exam_max = config.exam_max_score if config else 60
    term_locked = bool(active_term and active_term.is_locked)

    students = (
        Student.query.filter_by(class_arm_id=class_arm_id, is_active=True)
        .order_by(Student.full_name)
        .all()
    )

    scores_by_student = {}
    if active_term and active_session:
        existing_scores = Score.query.filter_by(
            subject_id=subject_id, term_id=active_term.id, session_id=active_session.id
        ).filter(Score.student_id.in_([s.id for s in students])).all()
        scores_by_student = {s.student_id: s for s in existing_scores}

    payload = [
        _serialize_student_score(student, scores_by_student.get(student.id), ca_max, exam_max)
        for student in students
    ]

    return jsonify({
        "success": True,
        "termLocked": term_locked,
        "caMax": ca_max,
        "examMax": exam_max,
        "students": payload,
    })


@api_bp.route("/teacher/scores", methods=["POST"])
@api_teacher_required
def save_teacher_scores():
    teacher_id = session["teacheronline"]
    payload = request.get_json(silent=True) or {}

    class_arm_id = payload.get("classArmId")
    subject_id = payload.get("subjectId")
    rows = payload.get("scores") or []

    if not class_arm_id or not subject_id:
        return jsonify({"success": False, "message": "classArmId and subjectId are required."}), 400

    # Step 1 — verify the teacher actually owns this assignment.
    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher_id, class_arm_id=class_arm_id, subject_id=subject_id
    ).first()
    if not assignment:
        return jsonify({"success": False, "message": "You are not assigned to this class and subject."}), 403

    # Step 2 — the active term must not be locked.
    active_session, active_term = _get_active_term()
    if not active_term or not active_session:
        return jsonify({"success": False, "message": "No active term/session is configured."}), 400
    if active_term.is_locked:
        return jsonify({
            "success": False,
            "message": "This term is locked. Contact an admin to unlock it before making changes.",
        }), 409

    config = SchoolConfig.query.first()
    ca_max = config.ca_max_score if config else 40
    exam_max = config.exam_max_score if config else 60

    # Only students who actually belong to this class arm may be written to —
    # a studentId from the request can't be used to write outside this class.
    valid_student_ids = {
        s.id for s in Student.query.filter_by(class_arm_id=class_arm_id, is_active=True).all()
    }

    # Step 3 — validate every row before writing anything.
    errors = []
    parsed_rows = []
    for row in rows:
        student_id = row.get("studentId")
        student = Student.query.get(student_id) if student_id else None
        label = student.full_name if student else f"student {student_id}"

        if student_id not in valid_student_ids:
            errors.append(f"{label}: not an active student in this class.")
            continue

        def _num(value):
            if value is None or value == "":
                return 0
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        ca1 = _num(row.get("ca1"))
        ca2 = _num(row.get("ca2"))
        ca3 = _num(row.get("ca3"))
        exam_score = _num(row.get("examScore"))

        if None in (ca1, ca2, ca3, exam_score):
            errors.append(f"{label}: scores must be numbers.")
            continue
        if ca1 < 0 or ca2 < 0 or ca3 < 0 or exam_score < 0:
            errors.append(f"{label}: scores cannot be negative.")
            continue
        if (ca1 + ca2 + ca3) > ca_max:
            errors.append(f"{label}: CA total exceeds the maximum of {ca_max}.")
            continue
        if exam_score > exam_max:
            errors.append(f"{label}: exam score exceeds the maximum of {exam_max}.")
            continue

        parsed_rows.append({
            "student_id": student_id, "ca1": ca1, "ca2": ca2, "ca3": ca3, "exam_score": exam_score,
        })

    if errors:
        return jsonify({"success": False, "message": "Some rows failed validation.", "errors": errors}), 400

    # Step 4 — all rows valid, write them.
    for row in parsed_rows:
        score = Score.query.filter_by(
            student_id=row["student_id"], subject_id=subject_id,
            term_id=active_term.id, session_id=active_session.id,
        ).first()
        if not score:
            score = Score(
                student_id=row["student_id"], subject_id=subject_id,
                term_id=active_term.id, session_id=active_session.id,
            )
            db.session.add(score)

        score.ca1 = row["ca1"]
        score.ca2 = row["ca2"]
        score.ca3 = row["ca3"]
        score.exam_score = row["exam_score"]
        score.teacher_id = teacher_id
        score.date_updated = datetime.utcnow()

    db.session.commit()

    # Step 5 — return the freshly recalculated state, same shape as the GET.
    students = (
        Student.query.filter_by(class_arm_id=class_arm_id, is_active=True)
        .order_by(Student.full_name)
        .all()
    )
    fresh_scores = Score.query.filter_by(
        subject_id=subject_id, term_id=active_term.id, session_id=active_session.id
    ).filter(Score.student_id.in_([s.id for s in students])).all()
    scores_by_student = {s.student_id: s for s in fresh_scores}

    result = [
        _serialize_student_score(student, scores_by_student.get(student.id), ca_max, exam_max)
        for student in students
    ]

    return jsonify({
        "success": True,
        "termLocked": active_term.is_locked,
        "caMax": ca_max,
        "examMax": exam_max,
        "students": result,
    })


@api_bp.route("/teacher/classes/<int:class_arm_id>/remarks", methods=["GET"])
@api_teacher_required
def teacher_get_class_remarks(class_arm_id):
    """Finalized results for this class arm, for the class-teacher-remark
    entry screen. Scoped the same way as score entry: a teacher must hold
    at least one TeacherSubjectAssignment for this class arm (any subject —
    this system has no separate "form teacher" concept, so any subject
    teacher assigned to the class may enter the class remark)."""
    teacher_id = session["teacheronline"]
    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher_id, class_arm_id=class_arm_id
    ).first()
    if not assignment:
        return jsonify({"success": False, "message": "You are not assigned to this class."}), 403

    active_session, active_term = _get_active_term()
    if not active_session or not active_term:
        return jsonify({"success": True, "results": []})

    results = (
        StudentTermResult.query.filter_by(
            term_id=active_term.id, session_id=active_session.id, status="finalized"
        )
        .join(Student, StudentTermResult.student_id == Student.id)
        .filter(Student.class_arm_id == class_arm_id, Student.is_active.is_(True))
        .order_by(Student.full_name)
        .all()
    )

    payload = [
        {
            "resultId": r.id,
            "fullName": r.student.full_name,
            "admissionNumber": r.student.admission_number,
            "classTeacherRemark": r.class_teacher_remark or "",
        }
        for r in results
    ]

    return jsonify({"success": True, "classArmLabel": assignment.class_arm.display_name, "results": payload})


@api_bp.route("/teacher/results/<int:result_id>/remarks", methods=["POST"])
@api_teacher_required
def teacher_update_remark(result_id):
    """A teacher may only set the class-teacher remark, and only for a
    finalized result belonging to a class they're assigned to — the same
    ownership check as everywhere else a result_id comes in from the client."""
    teacher_id = session["teacheronline"]
    result = StudentTermResult.query.get_or_404(result_id)

    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher_id, class_arm_id=result.student.class_arm_id
    ).first()
    if not assignment:
        return jsonify({"success": False, "message": "You are not assigned to this class."}), 403
    if result.status != "finalized":
        return jsonify({"success": False, "message": "This result has not been finalized yet."}), 404

    payload = request.get_json(silent=True) or {}
    remark = (payload.get("classTeacherRemark") or "").strip()
    if len(remark) > 1000:
        return jsonify({"success": False, "message": "Remark is too long (max 1000 characters)."}), 400

    result.class_teacher_remark = remark
    db.session.commit()

    return jsonify({"success": True, "classTeacherRemark": result.class_teacher_remark})

# ---------------------------------------------------------------------------
# FINALIZATION / RESULTS
# ---------------------------------------------------------------------------

@api_bp.route("/finalize/status", methods=["GET"])
@api_admin_required
def finalize_status():
    active_session, active_term = _get_active_term()
    if not active_session or not active_term:
        return jsonify({
            "success": True,
            "activeTerm": None,
            "activeSession": None,
            "classes": [],
        })

    arms = (
        ClassArm.query.join(ClassLevel, ClassArm.class_level_id == ClassLevel.id)
        .order_by(ClassLevel.order, ClassArm.name)
        .all()
    )

    classes = []
    for arm in arms:
        required_subjects = get_required_subjects(arm)
        required_subject_count = len(required_subjects)
        students = get_eligible_students(arm)
        total_students = len(students)

        complete_students = 0
        incomplete_names = []
        finalized_count = 0
        for student in students:
            complete = is_student_complete(student, required_subjects, active_term, active_session)
            if complete:
                complete_students += 1
            else:
                incomplete_names.append(student.full_name)

            result = StudentTermResult.query.filter_by(
                student_id=student.id, term_id=active_term.id, session_id=active_session.id
            ).first()
            if result and result.status == "finalized":
                finalized_count += 1

        is_finalized = total_students > 0 and finalized_count == total_students
        can_finalize = total_students > 0 and required_subject_count > 0

        classes.append({
            "classArmId": arm.id,
            "label": arm.display_name,
            "totalStudents": total_students,
            "completeStudents": complete_students,
            "requiredSubjectCount": required_subject_count,
            "isFinalized": is_finalized,
            "canFinalize": can_finalize,
            "incompleteStudentNames": [] if (is_finalized or complete_students == total_students) else incomplete_names,
        })

    return jsonify({
        "success": True,
        "activeTerm": active_term.name,
        "activeSession": active_session.name,
        "classes": classes,
    })


@api_bp.route("/finalize/<int:class_arm_id>", methods=["POST"])
@api_admin_required
def finalize_arm(class_arm_id):
    arm = ClassArm.query.get_or_404(class_arm_id)
    active_session, active_term = _get_active_term()

    if not active_session or not active_term:
        return jsonify({"success": False, "message": "No active session/term is configured."}), 400

    required_subjects = get_required_subjects(arm)
    if len(required_subjects) == 0:
        return jsonify({"success": False, "message": "This class has no subjects assigned."}), 400

    students = get_eligible_students(arm)
    if len(students) == 0:
        return jsonify({"success": False, "message": "This class has no active students."}), 400

    incomplete_count = sum(
        0 if is_student_complete(s, required_subjects, active_term, active_session) else 1
        for s in students
    )

    computed = finalize_class_arm(arm, active_term, active_session)

    return jsonify({
        "success": True,
        "finalizedCount": len(computed),
        "incompleteCount": incomplete_count,
    })


@api_bp.route("/results/<int:class_arm_id>/overview", methods=["GET"])
@api_admin_required
def results_overview(class_arm_id):
    arm = ClassArm.query.get_or_404(class_arm_id)
    active_session, active_term = _get_active_term()

    if not active_session or not active_term:
        return jsonify({
            "success": True,
            "classArmLabel": arm.display_name,
            "activeTerm": None,
            "activeSession": None,
            "isFinalized": False,
            "results": [],
        })

    results = (
        StudentTermResult.query.filter_by(
            term_id=active_term.id, session_id=active_session.id, status="finalized"
        )
        .join(Student, StudentTermResult.student_id == Student.id)
        .filter(Student.class_arm_id == arm.id, Student.is_active.is_(True))
        .all()
    )

    is_finalized = len(results) > 0
    results.sort(key=lambda r: (r.class_position if r.class_position is not None else 10 ** 9))

    payload = [
        {
            "resultId": r.id,
            "studentId": r.student_id,
            "position": r.class_position,
            "fullName": r.student.full_name,
            "admissionNumber": r.student.admission_number,
            "cumulativeTotal": r.cumulative_total,
            "cumulativeAverage": r.cumulative_average,
            "overallGrade": r.overall_grade,
        }
        for r in results
    ]

    return jsonify({
        "success": True,
        "classArmLabel": arm.display_name,
        "activeTerm": active_term.name,
        "activeSession": active_session.name,
        "isFinalized": is_finalized,
        "results": payload,
    })


@api_bp.route("/admin/results/<int:result_id>/remarks", methods=["POST"])
@api_admin_required
def admin_update_remarks(result_id):
    """Admin stands in for both the class-teacher and principal role here —
    can set either or both remarks in one call. Only fields present in the
    payload are touched, so this also works for saving just one field at a
    time from the UI."""
    result = StudentTermResult.query.get_or_404(result_id)
    if result.status != "finalized":
        return jsonify({"success": False, "message": "This result has not been finalized yet."}), 404

    payload = request.get_json(silent=True) or {}

    if "classTeacherRemark" in payload:
        remark = (payload.get("classTeacherRemark") or "").strip()
        if len(remark) > 1000:
            return jsonify({"success": False, "message": "Class teacher remark is too long (max 1000 characters)."}), 400
        result.class_teacher_remark = remark

    if "principalRemark" in payload:
        remark = (payload.get("principalRemark") or "").strip()
        if len(remark) > 1000:
            return jsonify({"success": False, "message": "Principal remark is too long (max 1000 characters)."}), 400
        result.principal_remark = remark

    db.session.commit()

    return jsonify({
        "success": True,
        "classTeacherRemark": result.class_teacher_remark,
        "principalRemark": result.principal_remark,
    })


# ---------------------------------------------------------------------------
# PORTAL
# ---------------------------------------------------------------------------

@api_bp.route("/portal/student", methods=["GET"])
@api_portal_required
def portal_student():
    student = Student.query.get_or_404(session["studentonline"])
    return jsonify({
        "success": True,
        "student": {
            "fullName": student.full_name,
            "admissionNumber": student.admission_number,
            "classLabel": student.class_arm.display_name if student.class_arm else None,
        },
    })


@api_bp.route("/portal/finalized-terms", methods=["GET"])
@api_portal_required
def portal_finalized_terms():
    student_id = session["studentonline"]
    results = (
        StudentTermResult.query.filter_by(student_id=student_id, status="finalized")
        .order_by(StudentTermResult.finalized_at.desc())
        .all()
    )

    terms = [
        {
            "resultId": r.id,
            "termLabel": r.term.name,
            "sessionLabel": r.session.name,
            "average": r.cumulative_average,
            "grade": r.overall_grade,
        }
        for r in results
    ]

    return jsonify({"success": True, "terms": terms})

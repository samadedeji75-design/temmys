from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# SCHOOL CONFIG
# ---------------------------------------------------------------------------

class SchoolConfig(db.Model):
    """Single-row table holding school-wide settings."""
    __tablename__ = "school_config"

    id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255))
    logo_path = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    motto = db.Column(db.String(200))  # optional tagline shown under the school name

    ca_max_score = db.Column(db.Integer, default=40)      # total CA out of
    exam_max_score = db.Column(db.Integer, default=60)    # exam out of

    active_session_id = db.Column(db.Integer, db.ForeignKey("session.id"))
    active_term_id = db.Column(db.Integer, db.ForeignKey("term.id"))

    active_session = db.relationship("Session", foreign_keys=[active_session_id])
    active_term = db.relationship("Term", foreign_keys=[active_term_id])


# ---------------------------------------------------------------------------
# SESSION / TERM
# ---------------------------------------------------------------------------

class Session(db.Model):
    __tablename__ = "session"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)  # "2025/2026"
    is_active = db.Column(db.Boolean, default=False)

    terms = db.relationship("Term", backref="session", lazy=True, cascade="all, delete-orphan")


class Term(db.Model):
    __tablename__ = "term"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)  # "First Term"
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    is_locked = db.Column(db.Boolean, default=False)  # blocks further edits + reveals to parents
    order = db.Column(db.Integer, nullable=False)  # 1 / 2 / 3 — drives third-term cumulative logic in app/services/results.py

    __table_args__ = (
        db.UniqueConstraint("name", "session_id", name="uq_term_per_session"),
        db.UniqueConstraint("session_id", "order", name="uq_term_order_per_session"),
    )


# ---------------------------------------------------------------------------
# CLASS STRUCTURE
# ---------------------------------------------------------------------------

class ClassLevel(db.Model):
    """e.g. SS1, SS2, JSS3 — the structural level, persists across years."""
    __tablename__ = "class_level"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    order = db.Column(db.Integer, default=0)  # for sorting JSS1 -> SS3

    arms = db.relationship("ClassArm", backref="class_level", lazy=True, cascade="all, delete-orphan")


class ClassArm(db.Model):
    """e.g. SS1 Gold, SS1 Diamond — the actual class students belong to."""
    __tablename__ = "class_arm"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # "Gold"
    class_level_id = db.Column(db.Integer, db.ForeignKey("class_level.id"), nullable=False)

    students = db.relationship("Student", backref="class_arm", lazy=True)
    class_subjects = db.relationship("ClassSubject", backref="class_arm", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("name", "class_level_id", name="uq_arm_per_level"),
    )

    @property
    def display_name(self):
        return f"{self.class_level.name} {self.name}"


# ---------------------------------------------------------------------------
# SUBJECTS
# ---------------------------------------------------------------------------

class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    code = db.Column(db.String(20))  # optional, e.g. "MTH"


class ClassSubject(db.Model):
    """Which subjects a given class arm offers."""
    __tablename__ = "class_subject"

    id = db.Column(db.Integer, primary_key=True)
    class_arm_id = db.Column(db.Integer, db.ForeignKey("class_arm.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)

    subject = db.relationship("Subject")

    __table_args__ = (
        db.UniqueConstraint("class_arm_id", "subject_id", name="uq_subject_per_class"),
    )


# ---------------------------------------------------------------------------
# TEACHERS
# ---------------------------------------------------------------------------

class Teacher(db.Model):
    __tablename__ = "teacher"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    password_encrypted = db.Column(db.Text)  # reversible copy for admin view — see app/services/security.py
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship("TeacherSubjectAssignment", backref="teacher", lazy=True, cascade="all, delete-orphan")


    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class TeacherSubjectAssignment(db.Model):
    """Scopes exactly what a teacher can enter scores for: this class, this subject."""
    __tablename__ = "teacher_subject_assignment"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    class_arm_id = db.Column(db.Integer, db.ForeignKey("class_arm.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)

    class_arm = db.relationship("ClassArm")
    subject = db.relationship("Subject")

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "class_arm_id", "subject_id", name="uq_teacher_assignment"),
    )


# ---------------------------------------------------------------------------
# STUDENTS
# ---------------------------------------------------------------------------

class Student(db.Model):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True)
    admission_number = db.Column(db.String(30), unique=True, nullable=False)  # login identifier
    full_name = db.Column(db.String(150), nullable=False)
    gender = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    guardian_name = db.Column(db.String(150))
    guardian_phone = db.Column(db.String(30))
    guardian_email = db.Column(db.String(150))

    class_arm_id = db.Column(db.Integer, db.ForeignKey("class_arm.id"), nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)  # parent/student portal login
    password_encrypted = db.Column(db.Text)  # reversible copy for admin view — see app/services/security.py
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    scores = db.relationship("Score", backref="student", lazy=True, cascade="all, delete-orphan")
    term_results = db.relationship("StudentTermResult", backref="student", lazy=True, cascade="all, delete-orphan")


    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


# ---------------------------------------------------------------------------
# GRADING SCALE
# ---------------------------------------------------------------------------

class GradingScale(db.Model):
    """Configurable score-range -> grade -> remark. Editable by admin, not hardcoded."""
    __tablename__ = "grading_scale"

    id = db.Column(db.Integer, primary_key=True)
    min_score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(5), nullable=False)   # "A", "B2", etc.
    remark = db.Column(db.String(50))                 # "Excellent"

    @staticmethod
    def get_grade(score):
        result = GradingScale.query.filter(
            GradingScale.min_score <= score,
            GradingScale.max_score >= score
        ).first()
        return result


# ---------------------------------------------------------------------------
# SCORES (the workhorse table)
# ---------------------------------------------------------------------------

class Score(db.Model):
    """
    One row = one student's performance in one subject, for one term/session.
    CA components stored individually so schools can see the breakdown,
    not just the sum.
    """
    __tablename__ = "score"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey("term.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)

    ca1 = db.Column(db.Float, default=0)
    ca2 = db.Column(db.Float, default=0)
    ca3 = db.Column(db.Float, default=0)
    exam_score = db.Column(db.Float, default=0)

    date_recorded = db.Column(db.DateTime, default=datetime.utcnow)
    date_updated = db.Column(db.DateTime, onupdate=datetime.utcnow)

    subject = db.relationship("Subject")
    term = db.relationship("Term")
    session = db.relationship("Session")
    teacher = db.relationship("Teacher")

    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", "term_id", "session_id", name="uq_score_per_subject_term"),
    )

    @property
    def ca_total(self):
        return round((self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0), 2)

    @property
    def subject_total(self):
        return round(self.ca_total + (self.exam_score or 0), 2)

    @property
    def subject_grade(self):
        grade_row = GradingScale.get_grade(self.subject_total)
        return grade_row.grade if grade_row else None

    @property
    def subject_remark(self):
        grade_row = GradingScale.get_grade(self.subject_total)
        return grade_row.remark if grade_row else None


# ---------------------------------------------------------------------------
# CUMULATIVE / TERM-LEVEL RESULT
# ---------------------------------------------------------------------------

class StudentTermResult(db.Model):
    """
    One row per student per term. Stores the computed cumulative snapshot
    and controls visibility to parents via `status`.
    Recomputed whenever scores change; finalized snapshot avoids
    recalculating on every parent page load.
    """
    __tablename__ = "student_term_result"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey("term.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)

    cumulative_total = db.Column(db.Float, default=0)
    cumulative_average = db.Column(db.Float, default=0)
    overall_grade = db.Column(db.String(5))
    class_position = db.Column(db.Integer)  # e.g. 3rd in class, computed on finalize

    class_teacher_remark = db.Column(db.Text)
    principal_remark = db.Column(db.Text)

    status = db.Column(db.String(20), default="draft")  # draft | finalized
    finalized_at = db.Column(db.DateTime)

    term = db.relationship("Term")
    session = db.relationship("Session")

    __table_args__ = (
        db.UniqueConstraint("student_id", "term_id", "session_id", name="uq_result_per_term"),
    )


# ---------------------------------------------------------------------------
# ADMIN USER (separate from teacher/parent auth)
# ---------------------------------------------------------------------------

class Admin(db.Model):
    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)
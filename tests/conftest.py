import pytest

from app import create_app
from app.models import (
    db,
    ClassArm,
    ClassLevel,
    ClassSubject,
    Session,
    SchoolConfig,
    Student,
    StudentTermResult,
    Subject,
    Teacher,
    TeacherSubjectAssignment,
    Term,
)


@pytest.fixture()
def app():
    app = create_app("testing")
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture()
def admin_client(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["adminonline"] = 1
        yield client


def make_teacher_client(app, teacher_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["teacheronline"] = teacher_id
    return client


@pytest.fixture()
def teacher_client_for(app):
    """Factory: teacher_client_for(teacher_id) returns a logged-in teacher client."""
    return lambda teacher_id: make_teacher_client(app, teacher_id)


class World:
    """Small helper that builds rows used across tests."""

    def __init__(self):
        self.counter = 0

    def _n(self):
        self.counter += 1
        return self.counter

    def level(self, name=None, section="secondary"):
        level = ClassLevel(name=name or f"Level {self._n()}", order=self._n(), section=section)
        db.session.add(level)
        db.session.commit()
        return level

    def arm(self, level, name="A"):
        arm = ClassArm(name=name, class_level_id=level.id)
        db.session.add(arm)
        db.session.commit()
        return arm

    def teacher(self, name=None, active=True):
        n = self._n()
        teacher = Teacher(full_name=name or f"Teacher {n}", email=f"t{n}@example.com", is_active=active)
        teacher.set_password("secret123")
        db.session.add(teacher)
        db.session.commit()
        return teacher

    def subject(self, name=None):
        subject = Subject(name=name or f"Subject {self._n()}")
        db.session.add(subject)
        db.session.commit()
        return subject

    def offer(self, arm, subject):
        db.session.add(ClassSubject(class_arm_id=arm.id, subject_id=subject.id))
        db.session.commit()

    def assign(self, teacher, arm, subject, source="manual"):
        row = TeacherSubjectAssignment(
            teacher_id=teacher.id, class_arm_id=arm.id, subject_id=subject.id, source=source
        )
        db.session.add(row)
        db.session.commit()
        return row

    def student(self, arm):
        n = self._n()
        student = Student(
            admission_number=f"ADM{n}", full_name=f"Student {n}", class_arm_id=arm.id, password_hash="x"
        )
        db.session.add(student)
        db.session.commit()
        return student

    def active_term(self):
        session_obj = Session(name="2026/2027", is_active=True)
        db.session.add(session_obj)
        db.session.commit()
        term = Term(name="First Term", session_id=session_obj.id, order=1)
        db.session.add(term)
        db.session.commit()
        config = SchoolConfig(
            school_name="Test School", active_session_id=session_obj.id, active_term_id=term.id
        )
        db.session.add(config)
        db.session.commit()
        return session_obj, term

    def finalized_result(self, student, session_obj, term):
        result = StudentTermResult(
            student_id=student.id,
            term_id=term.id,
            session_id=session_obj.id,
            class_arm_id=student.class_arm_id,
            status="finalized",
        )
        db.session.add(result)
        db.session.commit()
        return result


@pytest.fixture()
def world(app):
    return World()

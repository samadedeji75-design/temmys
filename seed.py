"""
seed.py — populates the database with enough sample data to build and test
the app against. Safe to re-run: it checks for existing rows before creating
duplicates, so running this twice won't blow up on unique constraints.

Usage:
    flask shell
    >>> from seed import run_seed
    >>> run_seed()

or as a standalone script if you wire up an app context:
    python seed.py
"""

from datetime import date

from app.models import (
    db,
    SchoolConfig,
    Session,
    Term,
    ClassLevel,
    ClassArm,
    Subject,
    ClassSubject,
    GradingScale,
    Admin,
    Teacher,
    TeacherSubjectAssignment,
    Student,
)


def get_or_create(model, defaults=None, **kwargs):
    """Avoids duplicate rows on re-run. Returns (instance, created_bool)."""
    instance = model.query.filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    db.session.add(instance)
    db.session.flush()  # get instance.id without a full commit yet
    return instance, True


def seed_school_config(session_obj, term_obj):
    config = SchoolConfig.query.first()
    if not config:
        config = SchoolConfig(
            school_name="Bright Future Secondary School",
            address="12 Ademola Street, Ibadan, Oyo State",
            logo_path="images/logo.png",
            ca_max_score=40,
            exam_max_score=60,
            active_session_id=session_obj.id,
            active_term_id=term_obj.id,
        )
        db.session.add(config)
    else:
        config.active_session_id = session_obj.id
        config.active_term_id = term_obj.id
    return config


def seed_sessions_and_terms():
    session_obj, _ = get_or_create(Session, name="2025/2026", defaults={"is_active": True})

    term_names = ["First Term", "Second Term", "Third Term"]
    terms = []
    for name in term_names:
        term, _ = get_or_create(
            Term,
            name=name,
            session_id=session_obj.id,
            defaults={"is_locked": False},
        )
        terms.append(term)

    active_term = terms[0]  # First Term is the active one for seed purposes
    return session_obj, active_term


def seed_grading_scale():
    bands = [
        (75, 100, "A1", "Excellent"),
        (70, 74, "B2", "Very Good"),
        (65, 69, "B3", "Good"),
        (60, 64, "C4", "Credit"),
        (55, 59, "C5", "Credit"),
        (50, 54, "C6", "Credit"),
        (45, 49, "D7", "Pass"),
        (40, 44, "E8", "Pass"),
        (0, 39, "F9", "Fail"),
    ]
    for min_score, max_score, grade, remark in bands:
        get_or_create(
            GradingScale,
            min_score=min_score,
            max_score=max_score,
            defaults={"grade": grade, "remark": remark},
        )


def seed_class_structure():
    levels_data = [
        ("JSS1", 1, ["Gold", "Silver"]),
        ("JSS2", 2, ["Gold", "Silver"]),
        ("JSS3", 3, ["Gold", "Silver"]),
        ("SS1", 4, ["Science", "Arts"]),
        ("SS2", 5, ["Science", "Arts"]),
        ("SS3", 6, ["Science", "Arts"]),
    ]

    all_arms = []
    for level_name, order, arm_names in levels_data:
        level, _ = get_or_create(ClassLevel, name=level_name, defaults={"order": order})
        for arm_name in arm_names:
            arm, _ = get_or_create(ClassArm, name=arm_name, class_level_id=level.id)
            all_arms.append(arm)

    return all_arms


def seed_subjects():
    subject_names = [
        ("Mathematics", "MTH"),
        ("English Language", "ENG"),
        ("Biology", "BIO"),
        ("Chemistry", "CHM"),
        ("Physics", "PHY"),
        ("Government", "GOV"),
        ("Economics", "ECO"),
        ("Literature in English", "LIT"),
        ("Agricultural Science", "AGR"),
        ("Computer Studies", "CMP"),
    ]
    subjects = []
    for name, code in subject_names:
        subject, _ = get_or_create(Subject, name=name, defaults={"code": code})
        subjects.append(subject)
    return subjects


def seed_class_subjects(all_arms, subjects):
    """Assign a reasonable subject spread per class arm rather than every
    subject to every class — mirrors how real schools split Science/Arts."""
    subject_by_name = {s.name: s for s in subjects}

    core = ["Mathematics", "English Language"]
    science_extra = ["Biology", "Chemistry", "Physics", "Agricultural Science", "Computer Studies"]
    arts_extra = ["Government", "Economics", "Literature in English", "Computer Studies"]

    for arm in all_arms:
        subject_names_for_arm = list(core)
        if arm.name in ("Science",):
            subject_names_for_arm += science_extra
        elif arm.name in ("Arts",):
            subject_names_for_arm += arts_extra
        else:
            # JSS classes get a broad general spread, not yet split into Science/Arts
            subject_names_for_arm += ["Biology", "Government", "Computer Studies", "Agricultural Science"]

        for name in subject_names_for_arm:
            subject = subject_by_name.get(name)
            if subject:
                get_or_create(ClassSubject, class_arm_id=arm.id, subject_id=subject.id)


def seed_admin():
    admin = Admin.query.filter_by(email="admin@brightfuture.edu.ng").first()
    if not admin:
        admin = Admin(full_name="School Administrator", email="admin@brightfuture.edu.ng")
        admin.set_password("ChangeMe123!")
        db.session.add(admin)
    return admin


def seed_teachers(all_arms, subjects):
    subject_by_name = {s.name: s for s in subjects}
    teacher_data = [
        ("Mrs. Adaeze Okonkwo", "adaeze.okonkwo@brightfuture.edu.ng", "Mathematics"),
        ("Mr. Tunde Bakare", "tunde.bakare@brightfuture.edu.ng", "English Language"),
        ("Mrs. Ngozi Eze", "ngozi.eze@brightfuture.edu.ng", "Biology"),
        ("Mr. Femi Ogundele", "femi.ogundele@brightfuture.edu.ng", "Chemistry"),
    ]

    teachers = []
    for full_name, email, subject_name in teacher_data:
        teacher = Teacher.query.filter_by(email=email).first()
        if not teacher:
            teacher = Teacher(full_name=full_name, email=email, is_active=True)
            teacher.set_password("Teacher123!")
            db.session.add(teacher)
            db.session.flush()  # get teacher.id, password_hash already set
        teachers.append(teacher)

        subject = subject_by_name.get(subject_name)
        if subject:
            # Assign this teacher to every class arm that offers this subject
            offering_arms = (
                ClassSubject.query.filter_by(subject_id=subject.id).all()
            )
            for class_subject in offering_arms:
                get_or_create(
                    TeacherSubjectAssignment,
                    teacher_id=teacher.id,
                    class_arm_id=class_subject.class_arm_id,
                    subject_id=subject.id,
                )
    return teachers


def seed_students(all_arms):
    """Creates a handful of students in the first couple of class arms only,
    just enough to exercise the score-entry and portal flows."""
    sample_names = [
        ("Chiamaka Nwosu", "F"),
        ("David Adeyemi", "M"),
        ("Fatima Yusuf", "F"),
        ("Emeka Umeh", "M"),
        ("Blessing Okafor", "F"),
        ("Ibrahim Sule", "M"),
    ]

    target_arms = all_arms[:2]  # JSS1 Gold, JSS1 Silver
    students = []
    admission_counter = 1001

    for arm in target_arms:
        for full_name, gender in sample_names:
            admission_number = f"BFS/{admission_counter}"
            student = Student.query.filter_by(admission_number=admission_number).first()
            if not student:
                student = Student(
                    admission_number=admission_number,
                    full_name=full_name,
                    gender=gender,
                    date_of_birth=date(2012, 1, 1),
                    guardian_name=f"Guardian of {full_name.split()[0]}",
                    guardian_phone="08000000000",
                    guardian_email=f"guardian{admission_counter}@example.com",
                    class_arm_id=arm.id,
                    is_active=True,
                )
                student.set_password("Student123!")
                db.session.add(student)
            students.append(student)
            admission_counter += 1

    return students


def run_seed():
    session_obj, active_term = seed_sessions_and_terms()
    seed_school_config(session_obj, active_term)
    seed_grading_scale()

    all_arms = seed_class_structure()
    subjects = seed_subjects()
    seed_class_subjects(all_arms, subjects)

    seed_admin()
    seed_teachers(all_arms, subjects)
    seed_students(all_arms)

    db.session.commit()
    print("Seed complete:")
    print(f"  Admin login: admin@brightfuture.edu.ng / ChangeMe123!")
    print(f"  Teacher login (sample): adaeze.okonkwo@brightfuture.edu.ng / Teacher123!")
    print(f"  Student portal login (sample): BFS/1001 / Student123!")


if __name__ == "__main__":
    # Requires an app context — matches your app package's create_app factory.
    from app import create_app

    app = create_app()
    with app.app_context():
        run_seed()
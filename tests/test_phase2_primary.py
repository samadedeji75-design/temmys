"""Phase 2: primary class auto-assignment."""
from app.models import ClassArm, ClassSubject, TeacherSubjectAssignment, db
from app.services.assignments import (
    describe_primary_replacement,
    sync_primary_arm,
)
from app.services import email as email_service


def assert_primary_invariant(arm):
    """I1 and I2 for a primary arm."""
    rows = TeacherSubjectAssignment.query.filter_by(class_arm_id=arm.id).all()
    offered = {cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id).all()}
    if arm.class_teacher_id is None:
        assert not [r for r in rows if r.source == "class_teacher"]
        return
    assert {(r.teacher_id, r.subject_id, r.source) for r in rows} == {
        (arm.class_teacher_id, sid, "class_teacher") for sid in offered
    }
    assert len(rows) == len(offered)


def primary_arm(world, subjects=3, name="Primary 3"):
    level = world.level(name, "primary")
    arm = world.arm(level, "Gold")
    subs = [world.subject() for _ in range(subjects)]
    for sub in subs:
        world.offer(arm, sub)
    return arm, subs


# ---------------------------------------------------------------------------
# sync_primary_arm
# ---------------------------------------------------------------------------

def test_sync_creates_one_row_per_subject_and_is_idempotent(world):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    arm.class_teacher_id = teacher.id
    sync_primary_arm(arm)
    db.session.commit()
    assert_primary_invariant(arm)
    assert TeacherSubjectAssignment.query.count() == 3
    sync_primary_arm(arm)
    db.session.commit()
    assert_primary_invariant(arm)
    assert TeacherSubjectAssignment.query.count() == 3


def test_sync_removes_rows_when_class_teacher_cleared(world):
    arm, _ = primary_arm(world)
    teacher = world.teacher()
    arm.class_teacher_id = teacher.id
    sync_primary_arm(arm)
    db.session.commit()
    arm.class_teacher_id = None
    sync_primary_arm(arm)
    db.session.commit()
    assert TeacherSubjectAssignment.query.count() == 0
    assert_primary_invariant(arm)


def test_sync_replaces_rows_when_teacher_changes(world):
    arm, _ = primary_arm(world)
    first, second = world.teacher(), world.teacher()
    arm.class_teacher_id = first.id
    sync_primary_arm(arm)
    db.session.commit()
    arm.class_teacher_id = second.id
    sync_primary_arm(arm)
    db.session.commit()
    assert {r.teacher_id for r in TeacherSubjectAssignment.query.all()} == {second.id}
    assert_primary_invariant(arm)


def test_sync_removes_legacy_manual_and_other_teachers_rows(world):
    arm, subs = primary_arm(world)
    boss, other = world.teacher(), world.teacher()
    world.assign(other, arm, subs[0])                  # other teacher
    world.assign(boss, arm, subs[1])                   # legacy manual row of the class teacher
    arm.class_teacher_id = boss.id
    sync_primary_arm(arm)
    db.session.commit()
    assert_primary_invariant(arm)
    assert TeacherSubjectAssignment.query.filter_by(teacher_id=other.id).count() == 0


def test_sync_removes_rows_for_subjects_not_offered(world):
    arm, subs = primary_arm(world)
    boss = world.teacher()
    extra = world.subject()
    world.assign(boss, arm, extra)                     # orphan: class does not offer it
    arm.class_teacher_id = boss.id
    sync_primary_arm(arm)
    db.session.commit()
    assert_primary_invariant(arm)


def test_sync_does_nothing_for_secondary_arm(world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    arm.class_teacher_id = teacher.id
    sync_primary_arm(arm)
    db.session.commit()
    assert TeacherSubjectAssignment.query.count() == 1
    assert TeacherSubjectAssignment.query.first().source == "manual"


def test_describe_primary_replacement(world):
    arm, subs = primary_arm(world)
    boss, other = world.teacher(), world.teacher("Mrs Ade")
    world.assign(other, arm, subs[0])
    world.assign(other, arm, subs[1])
    world.assign(boss, arm, subs[2])
    info = describe_primary_replacement(arm, boss.id)
    assert info["replaces"] == [{"teacherId": other.id, "teacherName": "Mrs Ade", "subjectCount": 2}]
    assert info["legacyManualCountForSameTeacher"] == 1


# ---------------------------------------------------------------------------
# Class teacher endpoint
# ---------------------------------------------------------------------------

def test_setting_class_teacher_assigns_all_subjects(admin_client, world):
    arm, _ = primary_arm(world)
    teacher = world.teacher()
    response = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    assert response.status_code == 200
    db.session.expire_all()
    assert_primary_invariant(ClassArm.query.get(arm.id))
    assert TeacherSubjectAssignment.query.count() == 3


def test_confirm_replace_flow(admin_client, world):
    arm, subs = primary_arm(world)
    old, new = world.teacher("Mrs Ade"), world.teacher()
    world.assign(old, arm, subs[0])
    world.assign(old, arm, subs[1])

    blocked = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": new.id})
    assert blocked.status_code == 409
    body = blocked.get_json()
    assert body["code"] == "confirm_replace"
    assert body["message"] == "Setting this class teacher will replace existing subject assignments in this class."
    assert body["replaces"] == [{"teacherId": old.id, "teacherName": "Mrs Ade", "subjectCount": 2}]
    db.session.expire_all()
    assert ClassArm.query.get(arm.id).class_teacher_id is None
    assert {r.teacher_id for r in TeacherSubjectAssignment.query.all()} == {old.id}

    done = admin_client.put(
        f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": new.id, "confirmReplace": True}
    )
    assert done.status_code == 200
    db.session.expire_all()
    assert_primary_invariant(ClassArm.query.get(arm.id))


def test_no_confirmation_needed_on_secondary_or_when_nothing_replaced(admin_client, world):
    secondary = world.arm(world.level())
    teacher, other = world.teacher(), world.teacher()
    subject = world.subject()
    world.offer(secondary, subject)
    world.assign(other, secondary, subject)
    assert admin_client.put(
        f"/api/classes/arms/{secondary.id}/class-teacher", json={"teacherId": teacher.id}
    ).status_code == 200
    assert TeacherSubjectAssignment.query.count() == 1  # secondary: other teacher's row untouched

    arm, _ = primary_arm(world, name="P 2")
    assert admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id}).status_code == 200


def test_clearing_class_teacher_removes_automatic_rows(admin_client, world):
    arm, _ = primary_arm(world)
    teacher = world.teacher()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": None})
    assert TeacherSubjectAssignment.query.count() == 0


# ---------------------------------------------------------------------------
# Class subjects keep the class teacher in sync
# ---------------------------------------------------------------------------

def test_adding_and_removing_subject_updates_primary_class_teacher(admin_client, world):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    new_subject = world.subject()

    ids = [s.id for s in subs] + [new_subject.id]
    assert admin_client.put(f"/api/classes/{arm.id}/subjects", json={"subjectIds": ids}).status_code == 200
    db.session.expire_all()
    assert TeacherSubjectAssignment.query.filter_by(subject_id=new_subject.id).count() == 1
    assert_primary_invariant(ClassArm.query.get(arm.id))

    # Phase 3: removing subjects the class teacher holds needs confirmation first.
    removal = {"subjectIds": [subs[0].id]}
    assert admin_client.put(f"/api/classes/{arm.id}/subjects", json=removal).status_code == 409
    removal["confirmRemoval"] = True
    assert admin_client.put(f"/api/classes/{arm.id}/subjects", json=removal).status_code == 200
    db.session.expire_all()
    assert TeacherSubjectAssignment.query.count() == 1
    assert_primary_invariant(ClassArm.query.get(arm.id))


def test_subject_changes_do_not_touch_secondary_assignments(admin_client, world):
    arm = world.arm(world.level())
    teacher = world.teacher()
    keep, drop = world.subject(), world.subject()
    world.offer(arm, keep)
    world.offer(arm, drop)
    world.assign(teacher, arm, keep)
    world.assign(teacher, arm, drop)
    admin_client.put(f"/api/classes/{arm.id}/subjects", json={"subjectIds": [keep.id]})
    assert TeacherSubjectAssignment.query.count() == 2  # Phase 3 handles secondary removal


# ---------------------------------------------------------------------------
# Manual edits blocked on primary classes
# ---------------------------------------------------------------------------

def test_manual_post_blocked_on_primary(admin_client, world):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    response = admin_client.post(
        f"/api/teachers/{teacher.id}/assignments", json={"classArmId": arm.id, "subjectId": subs[0].id}
    )
    assert response.status_code == 409
    assert response.get_json()["message"] == "This is a primary class. Set a class teacher instead."
    assert TeacherSubjectAssignment.query.count() == 0


def test_manual_post_still_works_on_secondary(admin_client, world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    response = admin_client.post(
        f"/api/teachers/{teacher.id}/assignments", json={"classArmId": arm.id, "subjectId": subject.id}
    )
    assert response.status_code == 201
    assert response.get_json()["assignment"]["source"] == "manual"


def test_delete_blocked_for_automatic_rows_but_not_legacy_manual(admin_client, world):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    auto = TeacherSubjectAssignment.query.first()
    blocked = admin_client.delete(f"/api/teacher-assignments/{auto.id}")
    assert blocked.status_code == 409
    assert blocked.get_json()["message"] == "This assignment comes from the class teacher. Change the class teacher instead."

    other_arm, other_subs = primary_arm(world, name="P 9")
    legacy_teacher = world.teacher()
    legacy = world.assign(legacy_teacher, other_arm, other_subs[0])
    assert admin_client.delete(f"/api/teacher-assignments/{legacy.id}").status_code == 200


# ---------------------------------------------------------------------------
# Section changes
# ---------------------------------------------------------------------------

def test_primary_to_secondary_converts_sources_and_keeps_rows(admin_client, world):
    arm, _ = primary_arm(world)
    teacher = world.teacher()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    response = admin_client.put(f"/api/classes/levels/{arm.class_level_id}", json={"section": "secondary"})
    assert response.status_code == 200
    rows = TeacherSubjectAssignment.query.all()
    assert len(rows) == 3
    assert {r.source for r in rows} == {"manual"}


def test_secondary_to_primary_syncs_arm_with_class_teacher(admin_client, world):
    level = world.level("P 4")
    arm = world.arm(level)
    boss, other = world.teacher(), world.teacher("Mrs Ade")
    subs = [world.subject() for _ in range(2)]
    for sub in subs:
        world.offer(arm, sub)
    world.assign(other, arm, subs[0])
    arm.class_teacher_id = boss.id
    db.session.commit()

    blocked = admin_client.put(f"/api/classes/levels/{level.id}", json={"section": "primary"})
    assert blocked.status_code == 409 and blocked.get_json()["code"] == "confirm_replace"
    db.session.expire_all()
    assert level.section == "secondary"
    assert TeacherSubjectAssignment.query.count() == 1

    done = admin_client.put(
        f"/api/classes/levels/{level.id}", json={"section": "primary", "confirmReplace": True}
    )
    assert done.status_code == 200
    db.session.expire_all()
    assert_primary_invariant(ClassArm.query.get(arm.id))


def test_secondary_to_primary_without_class_teacher_changes_nothing(admin_client, world):
    level = world.level()
    arm = world.arm(level)
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    assert admin_client.put(f"/api/classes/levels/{level.id}", json={"section": "primary"}).status_code == 200
    assert TeacherSubjectAssignment.query.count() == 1
    assert TeacherSubjectAssignment.query.first().source == "manual"


# ---------------------------------------------------------------------------
# Serialization and email
# ---------------------------------------------------------------------------

def test_serializers_show_source_and_class_teacher_of(admin_client, world):
    arm, _ = primary_arm(world, name="Primary 3")
    teacher = world.teacher()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    listing = admin_client.get("/api/teachers").get_json()["teachers"][0]
    assert listing["classTeacherOf"] == ["Primary 3 Gold"]
    assert listing["assignmentCount"] == 3
    rows = admin_client.get(f"/api/teachers/{teacher.id}/assignments").get_json()["assignments"]
    assert {r["source"] for r in rows} == {"class_teacher"}


def test_email_lines_collapse_class_teacher_rows(world):
    arm, _ = primary_arm(world, name="Primary 3")
    teacher = world.teacher()
    arm.class_teacher_id = teacher.id
    sync_primary_arm(arm)
    sec_level = world.level("SS 1")
    sec_arm = world.arm(sec_level, "Blue")
    sec_arm.class_teacher_id = teacher.id
    other_arm = world.arm(sec_level, "Red")
    subject = world.subject()
    world.offer(other_arm, subject)
    world.assign(teacher, other_arm, subject)
    db.session.commit()
    lines = email_service._teacher_assignment_lines(teacher)
    assert lines == sorted([
        "Primary 3 Gold (class teacher, all subjects)",
        "SS 1 Blue (class teacher, remarks)",
        f"SS 1 Red - {subject.name}",
    ])


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def test_primary_class_teacher_can_read_and_save_every_subject(admin_client, world, teacher_client_for):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    other_arm = world.arm(world.level("Other"))
    student = world.student(arm)
    world.active_term()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    client = teacher_client_for(teacher.id)
    for sub in subs:
        url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={sub.id}"
        assert client.get(url).status_code == 200
        saved = client.post("/api/teacher/scores", json={
            "classArmId": arm.id, "subjectId": sub.id,
            "scores": [{"studentId": student.id, "ca1": 5, "ca2": 5, "ca3": 5, "examScore": 30}],
        })
        assert saved.status_code != 403
    assert client.get(f"/api/teacher/scores?classArmId={other_arm.id}&subjectId={subs[0].id}").status_code == 403


def test_removed_class_teacher_loses_score_access(admin_client, world, teacher_client_for):
    arm, subs = primary_arm(world)
    teacher = world.teacher()
    world.active_term()
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    client = teacher_client_for(teacher.id)
    url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={subs[0].id}"
    assert client.get(url).status_code == 200
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": None})
    assert client.get(url).status_code == 403

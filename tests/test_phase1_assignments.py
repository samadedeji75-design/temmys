"""Phase 1: sections, class teacher, remark rule, clear assignments."""
from app.models import ClassArm, ClassLevel, Score, TeacherSubjectAssignment, db
from app.services.assignments import teacher_can_write_remarks


# ---------------------------------------------------------------------------
# teacher_can_write_remarks
# ---------------------------------------------------------------------------

def test_class_teacher_can_write_remarks_without_assignment(world):
    arm = world.arm(world.level())
    teacher = world.teacher()
    arm.class_teacher_id = teacher.id
    db.session.commit()
    assert teacher_can_write_remarks(teacher.id, arm.id) is True


def test_other_assigned_teacher_cannot_once_class_teacher_set(world):
    level = world.level()
    arm = world.arm(level)
    boss, other = world.teacher(), world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    world.assign(other, arm, subject)
    arm.class_teacher_id = boss.id
    db.session.commit()
    assert teacher_can_write_remarks(other.id, arm.id) is False


def test_fallback_when_no_class_teacher(world):
    arm = world.arm(world.level())
    teacher = world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    assert teacher_can_write_remarks(teacher.id, arm.id) is True


def test_no_class_teacher_and_no_assignment(world):
    arm = world.arm(world.level())
    teacher = world.teacher()
    assert teacher_can_write_remarks(teacher.id, arm.id) is False


def test_nonexistent_arm(world):
    teacher = world.teacher()
    assert teacher_can_write_remarks(teacher.id, 9999) is False


# ---------------------------------------------------------------------------
# Remark endpoints
# ---------------------------------------------------------------------------

def _remark_setup(world):
    arm = world.arm(world.level())
    class_teacher, subject_teacher = world.teacher(), world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    world.assign(subject_teacher, arm, subject)
    student = world.student(arm)
    session_obj, term = world.active_term()
    result = world.finalized_result(student, session_obj, term)
    return arm, class_teacher, subject_teacher, result


def test_remark_endpoints_respect_class_teacher(world, teacher_client_for):
    arm, class_teacher, subject_teacher, result = _remark_setup(world)
    arm.class_teacher_id = class_teacher.id
    db.session.commit()

    other = teacher_client_for(subject_teacher.id)
    assert other.get(f"/api/teacher/classes/{arm.id}/remarks").status_code == 403
    assert other.post(
        f"/api/teacher/results/{result.id}/remarks", json={"classTeacherRemark": "hi"}
    ).status_code == 403

    mine = teacher_client_for(class_teacher.id)
    response = mine.get(f"/api/teacher/classes/{arm.id}/remarks")
    assert response.status_code == 200
    assert response.get_json()["classArmLabel"] == arm.display_name
    saved = mine.post(
        f"/api/teacher/results/{result.id}/remarks", json={"classTeacherRemark": "Well done"}
    )
    assert saved.status_code == 200
    assert saved.get_json()["classTeacherRemark"] == "Well done"


def test_remark_fallback_without_class_teacher(world, teacher_client_for):
    arm, _class_teacher, subject_teacher, result = _remark_setup(world)
    client = teacher_client_for(subject_teacher.id)
    assert client.get(f"/api/teacher/classes/{arm.id}/remarks").status_code == 200
    assert client.post(
        f"/api/teacher/results/{result.id}/remarks", json={"classTeacherRemark": "ok"}
    ).status_code == 200


def test_remark_page_route(world, teacher_client_for):
    arm, class_teacher, subject_teacher, _ = _remark_setup(world)
    arm.class_teacher_id = class_teacher.id
    db.session.commit()
    assert teacher_client_for(subject_teacher.id).get(f"/teacher/classes/{arm.id}/remarks").status_code == 403
    assert teacher_client_for(class_teacher.id).get(f"/teacher/classes/{arm.id}/remarks").status_code == 200


# ---------------------------------------------------------------------------
# my-assignments
# ---------------------------------------------------------------------------

def test_my_assignments_remark_classes(world, teacher_client_for):
    level = world.level("SS 1")
    arm_a, arm_b, arm_c = world.arm(level, "Gold"), world.arm(level, "Blue"), world.arm(level, "Red")
    teacher, other = world.teacher(), world.teacher()
    subject = world.subject()
    for arm in (arm_a, arm_b, arm_c):
        world.offer(arm, subject)
    world.assign(teacher, arm_a, subject)          # fallback: arm_a has no class teacher
    world.assign(teacher, arm_b, subject)          # arm_b has a different class teacher
    arm_b.class_teacher_id = other.id
    arm_c.class_teacher_id = teacher.id            # class teacher, zero assignments
    db.session.commit()

    data = teacher_client_for(teacher.id).get("/api/teacher/my-assignments").get_json()
    assert data["success"] is True
    assert len(data["assignments"]) == 2
    assert data["remarkClasses"] == [
        {"classArmId": arm_a.id, "className": "SS 1 Gold", "isClassTeacher": False},
        {"classArmId": arm_c.id, "className": "SS 1 Red", "isClassTeacher": True},
    ]


def test_my_assignments_unchanged_fields(world, teacher_client_for):
    arm = world.arm(world.level())
    teacher = world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    row = teacher_client_for(teacher.id).get("/api/teacher/my-assignments").get_json()["assignments"][0]
    assert set(row) == {
        "classArmId", "className", "subjectId", "subjectName", "studentsTotal", "studentsWithScoresEntered",
    }


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

def test_admin_endpoints_require_login(client, world):
    arm = world.arm(world.level())
    assert client.put("/api/classes/levels/1", json={}).status_code == 401
    assert client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": None}).status_code == 401
    assert client.post(f"/api/classes/{arm.id}/clear-assignments", json={}).status_code == 401


def test_serializers_include_new_fields(admin_client, world):
    level = world.level("JSS 1")
    arm = world.arm(level, "A")
    data = admin_client.get("/api/classes").get_json()
    assert data["levels"][0]["section"] == "secondary"
    assert data["arms"][0]["classTeacherId"] is None
    assert data["arms"][0]["classTeacherName"] is None
    assert {"id", "levelId", "name", "studentCount"} <= set(data["arms"][0])


def test_create_level_section(admin_client):
    ok = admin_client.post("/api/classes/levels", json={"name": "Primary 1", "section": "primary"})
    assert ok.status_code == 201 and ok.get_json()["level"]["section"] == "primary"
    default = admin_client.post("/api/classes/levels", json={"name": "JSS 1"})
    assert default.get_json()["level"]["section"] == "secondary"
    bad = admin_client.post("/api/classes/levels", json={"name": "X", "section": "nursery"})
    assert bad.status_code == 400
    assert bad.get_json()["message"] == "Section must be primary or secondary."


def test_update_level(admin_client, world):
    level = world.level("JSS 1")
    other = world.level("JSS 2")
    ok = admin_client.put(f"/api/classes/levels/{level.id}", json={"name": "JSS One", "section": "primary"})
    assert ok.status_code == 200
    assert ok.get_json()["level"]["name"] == "JSS One"
    assert ok.get_json()["level"]["section"] == "primary"
    assert admin_client.put(f"/api/classes/levels/{level.id}", json={"name": other.name}).status_code == 409
    assert admin_client.put(f"/api/classes/levels/{level.id}", json={"section": "x"}).status_code == 400
    assert admin_client.put(f"/api/classes/levels/{level.id}", json={"name": " "}).status_code == 400
    assert admin_client.put("/api/classes/levels/9999", json={"name": "Z"}).status_code == 404


def test_section_change_does_not_touch_assignments_in_phase1(admin_client, world):
    level = world.level("P1")
    arm = world.arm(level)
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    admin_client.put(f"/api/classes/levels/{level.id}", json={"section": "primary"})
    assert TeacherSubjectAssignment.query.count() == 1


def test_set_class_teacher(admin_client, world):
    arm = world.arm(world.level())
    teacher = world.teacher("Mr Eze")
    ok = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})
    assert ok.status_code == 200
    assert ok.get_json()["arm"]["classTeacherId"] == teacher.id
    assert ok.get_json()["arm"]["classTeacherName"] == "Mr Eze"
    assert TeacherSubjectAssignment.query.count() == 0  # no rows created in Phase 1
    cleared = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": None})
    assert cleared.get_json()["arm"]["classTeacherId"] is None


def test_set_class_teacher_errors(admin_client, world):
    arm = world.arm(world.level())
    inactive = world.teacher(active=False)
    missing = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": 9999})
    assert missing.status_code == 404 and missing.get_json()["message"] == "Teacher not found."
    bad = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": "abc"})
    assert bad.status_code == 404
    inact = admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": inactive.id})
    assert inact.status_code == 400 and inact.get_json()["message"] == "That teacher is inactive."
    assert admin_client.put("/api/classes/arms/9999/class-teacher", json={"teacherId": None}).status_code == 404


def test_delete_arm_removes_assignments(admin_client, world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    assert admin_client.delete(f"/api/classes/arms/{arm.id}").status_code == 200
    assert TeacherSubjectAssignment.query.count() == 0
    assert ClassArm.query.count() == 0


def test_delete_arm_with_students_still_blocked(admin_client, world):
    arm = world.arm(world.level())
    world.student(arm)
    assert admin_client.delete(f"/api/classes/arms/{arm.id}").status_code == 409


# ---------------------------------------------------------------------------
# Arm move across sections
# ---------------------------------------------------------------------------

def test_move_across_sections_needs_confirmation(admin_client, world):
    secondary, primary = world.level("SS 1"), world.level("P 1", "primary")
    arm = world.arm(secondary)
    teacher, subject = world.teacher("Mrs Ade"), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    arm.class_teacher_id = teacher.id
    db.session.commit()

    blocked = admin_client.put(f"/api/classes/arms/{arm.id}", json={"levelId": primary.id, "name": "A"})
    assert blocked.status_code == 409
    body = blocked.get_json()
    assert body["code"] == "has_assignments"
    assert body["replaces"] == [{"teacherId": teacher.id, "teacherName": "Mrs Ade", "subjectCount": 1}]
    assert body["hasClassTeacher"] is True
    db.session.expire_all()
    assert ClassArm.query.get(arm.id).class_level_id == secondary.id
    assert TeacherSubjectAssignment.query.count() == 1

    moved = admin_client.put(
        f"/api/classes/arms/{arm.id}", json={"levelId": primary.id, "name": "A", "clearAssignments": True}
    )
    assert moved.status_code == 200
    db.session.expire_all()
    arm = ClassArm.query.get(arm.id)
    assert arm.class_level_id == primary.id
    assert arm.class_teacher_id is None
    assert TeacherSubjectAssignment.query.count() == 0


def test_same_section_move_and_rename_do_not_prompt(admin_client, world):
    one, two = world.level("SS 1"), world.level("SS 2")
    arm = world.arm(one)
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    arm.class_teacher_id = teacher.id
    db.session.commit()
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"levelId": two.id, "name": "B"}).status_code == 200
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"name": "C"}).status_code == 200
    db.session.expire_all()
    assert TeacherSubjectAssignment.query.count() == 1
    assert ClassArm.query.get(arm.id).class_teacher_id == teacher.id


def test_cross_section_move_with_nothing_to_clear_just_moves(admin_client, world):
    secondary, primary = world.level("SS 1"), world.level("P 1", "primary")
    arm = world.arm(secondary)
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"levelId": primary.id}).status_code == 200


def test_arm_update_validation(admin_client, world):
    level = world.level()
    arm, other = world.arm(level, "A"), world.arm(level, "B")
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"name": "B"}).status_code == 409
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"levelId": 9999}).status_code == 404
    assert admin_client.put(f"/api/classes/arms/{arm.id}", json={"levelId": "x"}).status_code == 404


# ---------------------------------------------------------------------------
# Clear assignments
# ---------------------------------------------------------------------------

def test_clear_requires_confirmation_and_keeps_data(admin_client, world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher("Mrs Ade"), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    response = admin_client.post(f"/api/classes/{arm.id}/clear-assignments", json={})
    assert response.status_code == 409
    assert response.get_json()["code"] == "confirm_clear"
    assert response.get_json()["replaces"][0]["teacherName"] == "Mrs Ade"
    assert TeacherSubjectAssignment.query.count() == 1


def test_clear_secondary_keeps_class_teacher_unless_asked(admin_client, world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    arm.class_teacher_id = teacher.id
    db.session.commit()

    done = admin_client.post(f"/api/classes/{arm.id}/clear-assignments", json={"confirm": True})
    assert done.status_code == 200 and done.get_json()["removed"] == 1
    assert done.get_json()["arm"]["classTeacherId"] == teacher.id
    assert TeacherSubjectAssignment.query.count() == 0

    again = admin_client.post(
        f"/api/classes/{arm.id}/clear-assignments", json={"confirm": True, "clearClassTeacher": True}
    )
    assert again.get_json()["arm"]["classTeacherId"] is None


def test_clear_primary_always_clears_class_teacher(admin_client, world):
    arm = world.arm(world.level("P 1", "primary"))
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    arm.class_teacher_id = teacher.id
    db.session.commit()
    done = admin_client.post(f"/api/classes/{arm.id}/clear-assignments", json={"confirm": True})
    assert done.get_json()["arm"]["classTeacherId"] is None


def test_clear_nothing_to_clear(admin_client, world):
    arm = world.arm(world.level())
    response = admin_client.post(f"/api/classes/{arm.id}/clear-assignments", json={})
    assert response.status_code == 200 and response.get_json()["removed"] == 0


def test_clear_keeps_scores(admin_client, world):
    arm = world.arm(world.level())
    teacher, subject = world.teacher(), world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    student = world.student(arm)
    session_obj, term = world.active_term()
    db.session.add(Score(
        student_id=student.id, subject_id=subject.id, term_id=term.id,
        session_id=session_obj.id, teacher_id=teacher.id, ca1=5, exam_score=40,
    ))
    db.session.commit()
    admin_client.post(f"/api/classes/{arm.id}/clear-assignments", json={"confirm": True})
    assert Score.query.count() == 1


def test_clear_unknown_arm(admin_client):
    assert admin_client.post("/api/classes/9999/clear-assignments", json={"confirm": True}).status_code == 404


# ---------------------------------------------------------------------------
# Existing behaviour unchanged
# ---------------------------------------------------------------------------

def test_score_entry_still_uses_assignment_rows(world, teacher_client_for):
    arm = world.arm(world.level())
    teacher, other = world.teacher(), world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    world.assign(teacher, arm, subject)
    url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={subject.id}"
    assert teacher_client_for(teacher.id).get(url).status_code != 403
    assert teacher_client_for(other.id).get(url).status_code == 403
    assert teacher_client_for(other.id).get(
        f"/teacher/classes/{arm.id}/subjects/{subject.id}/scores"
    ).status_code == 403


def test_class_teacher_without_assignment_cannot_enter_scores(world, teacher_client_for):
    arm = world.arm(world.level())
    teacher = world.teacher()
    subject = world.subject()
    world.offer(arm, subject)
    arm.class_teacher_id = teacher.id
    db.session.commit()
    url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={subject.id}"
    assert teacher_client_for(teacher.id).get(url).status_code == 403

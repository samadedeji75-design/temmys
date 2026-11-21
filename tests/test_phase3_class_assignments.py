"""Phase 3: class by class assignments, single-teacher rule, removal checks."""
from app.models import (
    ClassSubject,
    Score,
    TeacherSubjectAssignment,
    db,
)


def secondary_class(world, subjects=2):
    level = world.level("SS 1", "secondary")
    arm = world.arm(level, "Gold")
    subs = [world.subject(f"Subj {i}") for i in range(subjects)]
    for sub in subs:
        world.offer(arm, sub)
    return arm, subs


def rows(arm_id, subject_id=None):
    query = TeacherSubjectAssignment.query.filter_by(class_arm_id=arm_id)
    if subject_id is not None:
        query = query.filter_by(subject_id=subject_id)
    return query.all()


# ---------------------------------------------------------------- GET list

def test_get_assignments_lists_every_offered_subject(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    ade = world.teacher("Mrs Ade")
    world.assign(ade, arm, maths)

    data = admin_client.get(f"/api/classes/{arm.id}/assignments").get_json()
    assert data["success"] is True
    assert data["arm"]["label"] == "SS 1 Gold" and data["arm"]["section"] == "secondary"

    by_name = {s["subjectName"]: s for s in data["subjects"]}
    assert by_name[maths.name]["teacherName"] == "Mrs Ade"
    assert by_name[maths.name]["teacherActive"] is True
    assert by_name[maths.name]["source"] == "manual"
    assert by_name[maths.name]["duplicateTeachers"] == []
    assert by_name[english.name]["teacherId"] is None
    assert by_name[english.name]["assignmentId"] is None
    assert [s["subjectName"] for s in data["subjects"]] == sorted(by_name)


def test_get_assignments_shows_inactive_teacher_and_duplicates(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    old = world.teacher("Old Teacher", active=False)
    other = world.teacher("Mr Other")
    world.assign(old, arm, maths)
    world.assign(other, arm, maths)

    entry = next(
        s for s in admin_client.get(f"/api/classes/{arm.id}/assignments").get_json()["subjects"]
        if s["subjectId"] == maths.id
    )
    assert entry["teacherName"] == "Old Teacher" and entry["teacherActive"] is False
    assert entry["duplicateTeachers"] == ["Mr Other"]


def test_get_assignments_ignores_orphan_rows(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    stray = world.subject("Stray")
    world.assign(world.teacher(), arm, stray)  # class does not offer Stray
    data = admin_client.get(f"/api/classes/{arm.id}/assignments").get_json()
    assert stray.id not in [s["subjectId"] for s in data["subjects"]]


# ------------------------------------------------------------- PUT teacher

def test_put_teacher_set_change_and_clear(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    ade, bola = world.teacher("Mrs Ade"), world.teacher("Mr Bola")
    url = f"/api/classes/{arm.id}/subjects/{maths.id}/teacher"

    first = admin_client.put(url, json={"teacherId": ade.id})
    assert first.status_code == 200
    assert first.get_json()["subject"]["teacherName"] == "Mrs Ade"
    assert [r.teacher_id for r in rows(arm.id, maths.id)] == [ade.id]

    changed = admin_client.put(url, json={"teacherId": bola.id})
    assert changed.status_code == 200
    assert [r.teacher_id for r in rows(arm.id, maths.id)] == [bola.id]

    cleared = admin_client.put(url, json={"teacherId": None})
    assert cleared.status_code == 200
    assert cleared.get_json()["subject"]["teacherId"] is None
    assert rows(arm.id, maths.id) == []


def test_put_teacher_replaces_all_duplicates_and_resets_source(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    a, b, c = world.teacher(), world.teacher(), world.teacher()
    world.assign(a, arm, maths)
    world.assign(b, arm, maths)
    admin_client.put(f"/api/classes/{arm.id}/subjects/{maths.id}/teacher", json={"teacherId": b.id})
    remaining = rows(arm.id, maths.id)
    assert [(r.teacher_id, r.source) for r in remaining] == [(b.id, "manual")]


def test_put_teacher_validation(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    outsider = world.subject("Not offered")
    ade = world.teacher()
    inactive = world.teacher(active=False)

    base = f"/api/classes/{arm.id}/subjects"
    assert admin_client.put(f"{base}/{outsider.id}/teacher", json={"teacherId": ade.id}).status_code == 400
    assert admin_client.put(f"{base}/{maths.id}/teacher", json={"teacherId": inactive.id}).status_code == 400
    assert admin_client.put(f"{base}/{maths.id}/teacher", json={"teacherId": 99999}).status_code == 404
    assert admin_client.put(f"{base}/99999/teacher", json={"teacherId": ade.id}).status_code == 404
    assert admin_client.put("/api/classes/99999/subjects/1/teacher", json={"teacherId": ade.id}).status_code == 404
    assert admin_client.put(f"{base}/{maths.id}/teacher", json={"teacherId": "7"}).status_code == 400
    assert admin_client.put(f"{base}/{maths.id}/teacher", json={"teacherId": True}).status_code == 400
    assert rows(arm.id) == []


def test_put_teacher_blocked_on_primary_class(world, admin_client):
    level = world.level("Primary 4", "primary")
    arm = world.arm(level)
    sub = world.subject()
    world.offer(arm, sub)
    response = admin_client.put(
        f"/api/classes/{arm.id}/subjects/{sub.id}/teacher", json={"teacherId": world.teacher().id}
    )
    assert response.status_code == 409
    assert "primary class" in response.get_json()["message"].lower()


def test_phase3_endpoints_require_admin(world, client):
    arm, (maths, _) = secondary_class(world)
    assert client.get(f"/api/classes/{arm.id}/assignments").status_code == 401
    assert client.put(f"/api/classes/{arm.id}/subjects/{maths.id}/teacher", json={}).status_code == 401
    assert client.get("/api/assignments/conflicts").status_code == 401
    assert client.post("/api/assignments/cleanup-orphans", json={}).status_code == 401
    assert client.get("/admin/class-assignments").status_code == 302


# ---------------------------------------------------- single teacher rule

def test_old_endpoint_blocks_second_teacher_but_allows_same_teacher_many_classes(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    other_arm = world.arm(arm.class_level, "Blue")
    world.offer(other_arm, maths)
    ade, bola = world.teacher("Mrs Ade"), world.teacher("Mr Bola")

    ok = admin_client.post(
        f"/api/teachers/{ade.id}/assignments", json={"classArmId": arm.id, "subjectId": maths.id}
    )
    assert ok.status_code == 201

    clash = admin_client.post(
        f"/api/teachers/{bola.id}/assignments", json={"classArmId": arm.id, "subjectId": maths.id}
    )
    assert clash.status_code == 409
    message = clash.get_json()["message"]
    assert "already assigned to Mrs Ade" in message and "Class Assignments" in message
    assert len(rows(arm.id, maths.id)) == 1

    many = admin_client.post(
        f"/api/teachers/{ade.id}/assignments", json={"classArmId": other_arm.id, "subjectId": maths.id}
    )
    assert many.status_code == 201

    again = admin_client.post(
        f"/api/teachers/{ade.id}/assignments", json={"classArmId": arm.id, "subjectId": maths.id}
    )
    assert again.status_code == 409 and "already exists" in again.get_json()["message"]


# ----------------------------------------------------------------- issues

def test_conflicts_and_orphans_listed_and_cleaned(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    ade, bola = world.teacher("Mrs Ade"), world.teacher("Mr Bola")
    world.assign(ade, arm, maths)
    world.assign(bola, arm, maths)
    stray = world.subject("Stray")
    world.assign(ade, arm, stray)  # orphan: class does not offer Stray

    data = admin_client.get("/api/assignments/conflicts").get_json()
    assert len(data["conflicts"]) == 1
    conflict = data["conflicts"][0]
    assert conflict["className"] == "SS 1 Gold" and conflict["subjectName"] == maths.name
    assert {t["name"] for t in conflict["teachers"]} == {"Mrs Ade", "Mr Bola"}
    assert [o["subjectName"] for o in data["orphans"]] == ["Stray"]

    cleaned = admin_client.post("/api/assignments/cleanup-orphans", json={})
    assert cleaned.get_json()["removed"] == 1
    assert rows(arm.id, stray.id) == []
    assert len(rows(arm.id, maths.id)) == 2  # conflicts are never auto-resolved

    assert admin_client.get("/api/assignments/conflicts").get_json()["orphans"] == []


def test_no_issues_on_clean_data(world, admin_client):
    arm, (maths, _) = secondary_class(world)
    world.assign(world.teacher(), arm, maths)
    data = admin_client.get("/api/assignments/conflicts").get_json()
    assert data["conflicts"] == [] and data["orphans"] == []


# ---------------------------------------------------- class subject changes

def test_set_class_subjects_validation(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    url = f"/api/classes/{arm.id}/subjects"
    assert admin_client.put(url, json={}).status_code == 400
    assert admin_client.put(url, json={"subjectIds": "3"}).status_code == 400
    assert admin_client.put(url, json={"subjectIds": [maths.id, "x"]}).status_code == 400
    assert admin_client.put(url, json={"subjectIds": [True]}).status_code == 400
    assert {cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id)} == {maths.id, english.id}


def test_set_class_subjects_ignores_unknown_ids_and_returns_stored_ids(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    response = admin_client.put(
        f"/api/classes/{arm.id}/subjects", json={"subjectIds": [maths.id, 99999]}
    )
    assert response.status_code == 200
    assert response.get_json()["subjectIds"] == [maths.id]
    assert {cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id)} == {maths.id}


def test_removing_subject_with_teacher_needs_confirmation(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    ade = world.teacher("Mrs Ade")
    world.assign(ade, arm, maths)
    url = f"/api/classes/{arm.id}/subjects"

    refused = admin_client.put(url, json={"subjectIds": [english.id]})
    assert refused.status_code == 409
    body = refused.get_json()
    assert body["code"] == "confirm_removal" and body["success"] is False
    assert body["details"] == [
        {"subjectId": maths.id, "subjectName": maths.name, "teachers": ["Mrs Ade"], "scoreCount": 0}
    ]
    # Nothing changed.
    assert {cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id)} == {maths.id, english.id}
    assert len(rows(arm.id, maths.id)) == 1

    confirmed = admin_client.put(url, json={"subjectIds": [english.id], "confirmRemoval": True})
    assert confirmed.status_code == 200
    assert {cs.subject_id for cs in ClassSubject.query.filter_by(class_arm_id=arm.id)} == {english.id}
    assert rows(arm.id, maths.id) == []


def test_removing_subject_with_scores_keeps_scores(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    teacher = world.teacher()
    student = world.student(arm)
    session_obj, term = world.active_term()
    db.session.add(Score(
        student_id=student.id, subject_id=maths.id, term_id=term.id, session_id=session_obj.id,
        teacher_id=teacher.id, ca1=5, ca2=5, ca3=5, exam_score=40,
    ))
    db.session.commit()
    url = f"/api/classes/{arm.id}/subjects"

    refused = admin_client.put(url, json={"subjectIds": [english.id]})
    assert refused.status_code == 409
    detail = refused.get_json()["details"][0]
    assert detail["scoreCount"] == 1 and detail["teachers"] == []

    assert admin_client.put(url, json={"subjectIds": [english.id], "confirmRemoval": True}).status_code == 200
    assert Score.query.filter_by(subject_id=maths.id).count() == 1


def test_removing_unused_subject_needs_no_confirmation(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    response = admin_client.put(f"/api/classes/{arm.id}/subjects", json={"subjectIds": [english.id]})
    assert response.status_code == 200


def test_adding_subjects_never_needs_confirmation(world, admin_client):
    arm, (maths, english) = secondary_class(world)
    extra = world.subject("Extra")
    response = admin_client.put(
        f"/api/classes/{arm.id}/subjects", json={"subjectIds": [maths.id, english.id, extra.id]}
    )
    assert response.status_code == 200
    assert response.get_json()["subjectIds"] == sorted([maths.id, english.id, extra.id])


def test_primary_removal_confirms_then_syncs_class_teacher(world, admin_client):
    level = world.level("Primary 5", "primary")
    arm = world.arm(level)
    a, b = world.subject("A"), world.subject("B")
    world.offer(arm, a)
    world.offer(arm, b)
    teacher = world.teacher("Mrs Ade")
    admin_client.put(f"/api/classes/arms/{arm.id}/class-teacher", json={"teacherId": teacher.id})

    url = f"/api/classes/{arm.id}/subjects"
    assert admin_client.put(url, json={"subjectIds": [a.id]}).status_code == 409
    assert admin_client.put(url, json={"subjectIds": [a.id], "confirmRemoval": True}).status_code == 200
    remaining = rows(arm.id)
    assert [(r.subject_id, r.teacher_id, r.source) for r in remaining] == [(a.id, teacher.id, "class_teacher")]


# --------------------------------------------------------------- security

def test_removed_assignment_blocks_score_entry_immediately(world, admin_client, teacher_client_for):
    arm, (maths, _) = secondary_class(world)
    ade = world.teacher("Mrs Ade")
    url = f"/api/classes/{arm.id}/subjects/{maths.id}/teacher"
    admin_client.put(url, json={"teacherId": ade.id})

    teacher = teacher_client_for(ade.id)
    scores_url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={maths.id}"
    assert teacher.get(scores_url).status_code != 403

    admin_client.put(url, json={"teacherId": None})
    assert teacher.get(scores_url).status_code == 403


def test_replaced_teacher_loses_access_and_new_teacher_gains_it(world, admin_client, teacher_client_for):
    arm, (maths, _) = secondary_class(world)
    ade, bola = world.teacher(), world.teacher()
    url = f"/api/classes/{arm.id}/subjects/{maths.id}/teacher"
    admin_client.put(url, json={"teacherId": ade.id})
    admin_client.put(url, json={"teacherId": bola.id})
    scores_url = f"/api/teacher/scores?classArmId={arm.id}&subjectId={maths.id}"
    assert teacher_client_for(ade.id).get(scores_url).status_code == 403
    assert teacher_client_for(bola.id).get(scores_url).status_code != 403


def test_pages_render(world, admin_client):
    assert admin_client.get("/admin/class-assignments").status_code == 200
    assert admin_client.get("/admin/assignments").status_code == 200
    assert admin_client.get("/admin/class-subjects").status_code == 200

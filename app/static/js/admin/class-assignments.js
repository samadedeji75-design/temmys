/* ==========================================================================
   class-assignments.js - Class by class view of who teaches what.
   Uses:
     GET  /api/classes, GET /api/teachers
     GET  /api/classes/<id>/assignments
     PUT  /api/classes/<id>/subjects/<subjectId>/teacher
     PUT  /api/classes/arms/<id>/class-teacher
     POST /api/classes/<id>/clear-assignments
     GET  /api/assignments/conflicts, POST /api/assignments/cleanup-orphans
   ========================================================================== */

$(function () {
  let levels = [];
  let arms = [];
  let teachers = [];
  let currentArmId = null;
  let currentData = null;

  const $picker = $("#classPicker");
  const $card = $("#classCard");
  const $noClass = $("#noClassState");
  const $body = $("#subjectsBody");

  function activeTeachers() {
    return teachers.filter(function (t) { return t.isActive; });
  }

  /* ----------------------------------------------------------------- setup */

  function buildPicker() {
    $picker.empty().append($("<option>").val("").text("Choose a class..."));
    levels.forEach(function (level) {
      const group = $("<optgroup>").attr(
        "label", level.name + (level.section === "primary" ? " (Primary)" : " (Secondary)")
      );
      arms.filter(function (a) { return a.levelId === level.id; }).forEach(function (arm) {
        group.append($("<option>").val(arm.id).text(level.name + " " + arm.name));
      });
      if (group.children().length) $picker.append(group);
    });
  }

  function loadBase() {
    $.when(window.apiRequest("GET", "/api/classes"), window.apiRequest("GET", "/api/teachers"))
      .done(function (classesResp, teachersResp) {
        const c = classesResp[0];
        const t = teachersResp[0];
        if (!c.success || !t.success) return;
        levels = c.levels;
        arms = c.arms;
        teachers = t.teachers;
        buildPicker();

        const fromUrl = Number(new URLSearchParams(window.location.search).get("armId"));
        if (fromUrl && arms.some(function (a) { return a.id === fromUrl; })) {
          $picker.val(String(fromUrl));
          loadClass(fromUrl);
        }
      });
    loadIssues();
  }

  /* ---------------------------------------------------------------- issues */

  function loadIssues() {
    window.apiRequest("GET", "/api/assignments/conflicts").done(function (response) {
      const $area = $("#issuesArea").empty();
      if (!response || !response.success) return;

      if (response.orphans.length) {
        const sample = response.orphans.slice(0, 5).map(function (o) {
          return o.teacherName + ": " + o.className + " " + o.subjectName;
        }).join("; ");
        const $alert = $('<div class="alert alert-warning mb-4"></div>');
        $alert.append($("<div>").css("font-weight", "600").text(
          response.orphans.length + " assignment(s) point to subjects their class no longer offers."
        ));
        $alert.append($("<div>").text(sample + (response.orphans.length > 5 ? " and more." : ".")));
        $alert.append(
          $('<button type="button" class="btn btn-secondary btn-sm mt-2"></button>')
            .text("Clean up")
            .on("click", cleanupOrphans)
        );
        $area.append($alert);
      }

      if (response.conflicts.length) {
        const $alert = $('<div class="alert alert-warning mb-4"></div>');
        $alert.append($("<div>").css("font-weight", "600").text(
          response.conflicts.length + " class-subject(s) have more than one teacher."
        ));
        response.conflicts.forEach(function (c) {
          const names = c.teachers.map(function (t) { return t.name; }).join(", ");
          const $line = $('<div class="d-flex align-center gap-2" style="margin-top: var(--space-2);"></div>');
          $line.append($("<span>").text(
            c.className + " " + c.subjectName + ": " + names +
            (c.section === "primary" ? " (set the class teacher to fix)" : "")
          ));
          $line.append(
            $('<button type="button" class="btn btn-secondary btn-sm"></button>')
              .text("Open class")
              .on("click", function () {
                $picker.val(String(c.classArmId));
                loadClass(c.classArmId);
              })
          );
          $alert.append($line);
        });
        $area.append($alert);
      }
    });
  }

  function cleanupOrphans() {
    window.confirmAction({
      title: "Clean up assignments?",
      body: "These assignments are for subjects the class no longer offers. Removing them does not affect any scores.",
      confirmLabel: "Clean up",
      danger: true,
      onConfirm: function () {
        window.apiRequest("POST", "/api/assignments/cleanup-orphans", {}).done(function (response) {
          if (response && response.success) {
            window.showToast(response.removed + " assignment(s) removed.", "success");
            loadIssues();
            if (currentArmId) loadClass(currentArmId);
          }
        });
      }
    });
  }

  /* ------------------------------------------------------------ class view */

  function loadClass(armId) {
    currentArmId = armId;
    window.apiRequest("GET", "/api/classes/" + armId + "/assignments").done(function (response) {
      if (!response || !response.success) return;
      currentData = response;
      renderClass();
    });
  }

  function teacherLabel(name, active) {
    return active === false ? name + " (inactive)" : name;
  }

  function buildTeacherSelect($select, emptyLabel, selectedId, selectedName, selectedActive) {
    $select.empty().append($("<option>").val("").text(emptyLabel));
    activeTeachers().forEach(function (t) {
      $select.append($("<option>").val(t.id).text(t.fullName));
    });
    if (selectedId && selectedActive === false) {
      // Keep a deactivated teacher visible so the admin can see and replace them.
      $select.append($("<option>").val(selectedId).text(teacherLabel(selectedName, false)));
    }
    $select.val(selectedId ? String(selectedId) : "");
  }

  function renderClass() {
    const data = currentData;
    const isPrimary = data.arm.section === "primary";

    $noClass.hide();
    $card.prop("hidden", false);
    $("#classTitle").text(data.arm.label);
    $("#classSectionBadge")
      .removeClass("badge-info badge-neutral")
      .addClass(isPrimary ? "badge-info" : "badge-neutral")
      .text(isPrimary ? "Primary" : "Secondary");

    const classTeacher = teachers.find(function (t) { return t.id === data.arm.classTeacherId; });
    buildTeacherSelect(
      $("#classTeacherSelect"), "No class teacher",
      data.arm.classTeacherId, data.arm.classTeacherName, classTeacher ? classTeacher.isActive : true
    );
    $("#classTeacherSelect").data("current", data.arm.classTeacherId ? String(data.arm.classTeacherId) : "");
    $("#classTeacherHelp").text(
      isPrimary
        ? "This teacher teaches every subject in this class and writes the class remark."
        : "This teacher writes the class remark on report cards."
    );

    $body.empty();
    const subjects = data.subjects;
    $("#noSubjectsState").prop("hidden", subjects.length > 0);
    $("#subjectsWrap").prop("hidden", subjects.length === 0);

    if (isPrimary) {
      $("#assignSummary").text("");
      $("#primaryNotice")
        .prop("hidden", false)
        .text(
          data.arm.classTeacherId
            ? "All subjects are taught by " + data.arm.classTeacherName + ". Change the class teacher above to change this."
            : "Choose a class teacher to assign all subjects."
        );
      subjects.forEach(function (s) {
        const $row = $("<tr>");
        $row.append($("<td>").text(s.subjectName));
        $row.append($("<td>").addClass("cell-muted").text(
          data.arm.classTeacherName ? "Taught by " + data.arm.classTeacherName : "No teacher yet"
        ));
        $body.append($row);
      });
      return;
    }

    $("#primaryNotice").prop("hidden", true);
    const assigned = subjects.filter(function (s) { return s.teacherId !== null; }).length;
    $("#assignSummary").text(assigned + " of " + subjects.length + " subjects have a teacher");

    subjects.forEach(function (s) {
      const $row = $("<tr>").attr("data-subject-id", s.subjectId);
      if (s.teacherId === null) $row.css("background", "var(--color-warning-bg)");

      $row.append($("<td>").css("font-weight", "600").text(s.subjectName));

      const $select = $('<select class="form-select js-subject-teacher"></select>')
        .attr("data-subject-id", s.subjectId)
        .css({ minWidth: "200px", width: "100%" });
      buildTeacherSelect($select, "Unassigned", s.teacherId, s.teacherName, s.teacherActive);
      $select.data("current", s.teacherId ? String(s.teacherId) : "");

      const $cell = $("<td>").append($select);
      if (s.duplicateTeachers && s.duplicateTeachers.length) {
        $cell.append(
          $('<div class="form-hint text-danger"></div>').text(
            "Also assigned to " + s.duplicateTeachers.join(", ") + ". Choosing a teacher here replaces all of them."
          )
        );
      }
      $row.append($cell);
      $body.append($row);
    });
  }

  /* ------------------------------------------------------- subject teacher */

  function putSubjectTeacher(subjectId, teacherId, $select, previous) {
    $select.prop("disabled", true);
    window.apiRequest("PUT", "/api/classes/" + currentArmId + "/subjects/" + subjectId + "/teacher", {
      teacherId: teacherId
    })
      .done(function (response) {
        if (response && response.success) {
          currentData.subjects = currentData.subjects.map(function (s) {
            return s.subjectId === subjectId ? response.subject : s;
          });
          renderClass();
          window.showToast("Saved.", "success");
          loadIssues();
        }
      })
      .fail(function () {
        $select.val(previous);
      })
      .always(function () {
        $select.prop("disabled", false);
      });
  }

  $(document).on("change", ".js-subject-teacher", function () {
    const $select = $(this);
    const subjectId = Number($select.data("subject-id"));
    const previous = String($select.data("current") || "");
    const value = $select.val();

    if (value === "") {
      const subject = currentData.subjects.find(function (s) { return s.subjectId === subjectId; });
      $select.val(previous);
      window.confirmAction({
        title: "Remove the teacher?",
        body: "Nobody will be able to enter " + subject.subjectName + " scores for this class until you assign a teacher.",
        confirmLabel: "Remove teacher",
        danger: true,
        onConfirm: function () { putSubjectTeacher(subjectId, null, $select, previous); }
      });
      return;
    }
    putSubjectTeacher(subjectId, Number(value), $select, previous);
  });

  /* ---------------------------------------------------------- class teacher */

  function saveClassTeacher(teacherId, confirmReplace, previous) {
    const $select = $("#classTeacherSelect");
    $select.prop("disabled", true);
    window.apiRequest("PUT", "/api/classes/arms/" + currentArmId + "/class-teacher", {
      teacherId: teacherId,
      confirmReplace: !!confirmReplace
    })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Class teacher saved.", "success");
          loadClass(currentArmId);
          loadIssues();
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        $select.val(previous);
        if (xhr.status === 409 && data.code === "confirm_replace") {
          const parts = (data.replaces || []).map(function (r) {
            return r.teacherName + " (" + r.subjectCount + " subject" + (r.subjectCount === 1 ? "" : "s") + ")";
          });
          window.confirmAction({
            title: "Replace existing assignments?",
            body: "These teachers currently hold subjects in this class and will lose them: " +
              parts.join(", ") + ". The new class teacher will teach every subject in the class.",
            confirmLabel: "Replace",
            danger: true,
            onConfirm: function () { saveClassTeacher(teacherId, true, previous); }
          });
        }
      })
      .always(function () {
        $select.prop("disabled", false);
      });
  }

  $("#classTeacherSelect").on("change", function () {
    const previous = String($(this).data("current") || "");
    const value = $(this).val();
    saveClassTeacher(value ? Number(value) : null, false, previous);
  });

  /* -------------------------------------------------------------- clearing */

  $("#clearClassBtn").on("click", function () {
    if (!currentArmId) return;
    const armId = currentArmId;
    window.apiRequest("POST", "/api/classes/" + armId + "/clear-assignments", {})
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Nothing to clear.", "success");
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status !== 409 || data.code !== "confirm_clear") return;

        const parts = (data.replaces || []).map(function (r) {
          return r.teacherName + " (" + r.subjectCount + ")";
        });
        window.confirmAction({
          title: "Clear assignments?",
          body: "This removes every teacher assignment in this class" +
            (parts.length ? ": " + parts.join(", ") : "") +
            ". Scores are kept." +
            (currentData.arm.section === "primary" && data.hasClassTeacher ? " The class teacher is cleared too." : ""),
          confirmLabel: "Clear",
          danger: true,
          onConfirm: function () {
            window.apiRequest("POST", "/api/classes/" + armId + "/clear-assignments", { confirm: true })
              .done(function (response) {
                if (response && response.success) {
                  window.showToast("Assignments cleared.", "success");
                  loadClass(armId);
                  loadIssues();
                }
              });
          }
        });
      });
  });

  /* ------------------------------------------------------------------ init */

  $picker.on("change", function () {
    const value = $picker.val();
    if (!value) {
      currentArmId = null;
      $card.prop("hidden", true);
      $noClass.show();
      return;
    }
    loadClass(Number(value));
  });

  $card.prop("hidden", true);
  loadBase();
});

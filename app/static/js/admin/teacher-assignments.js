/* ==========================================================================
   teacher-assignments.js - Give one teacher a subject across many classes
   in one action. Uses:
     GET  /api/teachers, /api/classes, /api/subjects
     GET  /api/subjects/<id>/availability
     GET  /api/teachers/<id>/assignments
     POST /api/teachers/<id>/assignments/bulk
     DELETE /api/teacher-assignments/<id>
   ========================================================================== */

$(function () {
  const $teacherPicker = $("#teacherPicker");
  const $builder = $("#assignmentBuilder");
  const $noTeacherState = $("#noTeacherSelectedState");
  const $classGrid = $("#classGrid");
  const $subjectPicker = $("#subjectPicker");
  const $assignBtn = $("#assignSelectedBtn");
  const $tbody = $("#assignmentsTableBody");
  const $table = $("#assignmentsTable").closest(".table-wrapper");
  const $empty = $("#assignmentsEmptyState");

  let teachers = [];
  let classArms = []; // [{id, label, levelId, isPrimary}]
  let levels = [];
  let availability = {}; // classArmId -> {offered, teacherId, teacherName}
  let subjects = [];  // [{id, name, code}]
  let assignments = [];
  let selectedTeacherId = null;

  function populateTeacherPicker() {
    $teacherPicker.empty().append('<option value="">Choose a teacher&hellip;</option>');
    teachers.forEach(function (t) {
      $teacherPicker.append('<option value="' + t.id + '">' + t.fullName + " (" + t.email + ")</option>");
    });
  }

  function populateSubjectPicker() {
    $subjectPicker.empty();
    subjects.forEach(function (s) {
      $subjectPicker.append($("<option>").val(s.id).text(s.name));
    });
    const secondary = classArms.filter(function (arm) { return !arm.isPrimary; });
    $("#primaryOnlyHint").prop("hidden", !(classArms.length > 0 && secondary.length === 0));
  }

  function loadAvailability() {
    const subjectId = Number($subjectPicker.val());
    availability = {};
    if (!subjectId) {
      renderClassGrid();
      return;
    }
    window.apiRequest("GET", "/api/subjects/" + subjectId + "/availability").done(function (data) {
      if (!data || !data.success) return;
      data.arms.forEach(function (item) { availability[item.classArmId] = item; });
      renderClassGrid();
    });
  }

  // Disabled states: not offered, held by another teacher, or already mine.
  function stateFor(arm) {
    const info = availability[arm.id];
    if (!info || !info.offered) return { disabled: true, checked: false, hint: "Not offered" };
    if (info.teacherId && info.teacherId === selectedTeacherId) {
      return { disabled: true, checked: true, hint: "Already assigned" };
    }
    if (info.teacherId) return { disabled: true, checked: false, hint: info.teacherName };
    return { disabled: false, checked: false, hint: "" };
  }

  function renderClassGrid() {
    $classGrid.empty();
    levels.forEach(function (level) {
      if (level.section === "primary") return;
      const levelArms = classArms.filter(function (a) { return a.levelId === level.id; });
      if (levelArms.length === 0) return;

      const $group = $('<div class="class-grid-level">').attr("data-level-id", level.id);
      const $head = $('<div class="class-grid-level-head">');
      $head.append($('<span class="class-grid-level-name">').text(level.name));
      $head.append(
        $('<button type="button" class="btn btn-outline-secondary btn-sm js-select-level">').text("Select all in this level")
      );
      const $items = $('<div class="class-grid-items">');

      levelArms.forEach(function (arm) {
        const st = stateFor(arm);
        const $label = $('<label class="class-grid-item">')
          .toggleClass("is-disabled", st.disabled)
          .toggleClass("is-checked", st.checked);
        const $box = $('<input type="checkbox" class="js-class-box">')
          .val(arm.id).prop("disabled", st.disabled).prop("checked", st.checked);
        const $text = $("<span>").append($('<span class="label">').text(arm.label));
        if (st.hint) $text.append($('<span class="hint">').text(st.hint));
        $items.append($label.append($box, $text));
      });

      $classGrid.append($group.append($head, $items));
    });
    updateAssignButton();
  }

  function selectedArmIds() {
    return $classGrid.find(".js-class-box:checked:not(:disabled)").map(function () {
      return Number($(this).val());
    }).get();
  }

  function updateAssignButton() {
    const count = selectedArmIds().length;
    $assignBtn.prop("disabled", count === 0);
    $("#assignSelectedLabel").text(count > 0 ? "Assign selected (" + count + ")" : "Assign selected");
  }

  function renderAssignments() {
    $tbody.empty();

    if (assignments.length === 0) {
      $table.hide();
      $empty.show();
      return;
    }
    $table.show();
    $empty.hide();

    assignments.forEach(function (a) {
      const automatic = a.source === "class_teacher";
      const $row = $(
        '<tr data-id="' + a.id + '">' +
          "<td>" + $("<div>").text(a.className || "").html() + "</td>" +
          "<td>" + $("<div>").text(a.subjectName || "").html() +
            (automatic ? ' <span class="badge badge-info">Class teacher (automatic)</span>' : "") +
          "</td>" +
          '<td class="row-actions">' +
            (automatic ? "" : '<button type="button" class="btn btn-outline-danger btn-sm js-remove-assignment"><i class="bi bi-trash"></i></button>') +
          "</td>" +
        "</tr>"
      );
      $tbody.append($row);
    });
  }

  function loadAssignments() {
    if (!selectedTeacherId) return;
    window.apiRequest("GET", "/api/teachers/" + selectedTeacherId + "/assignments").done(function (response) {
      if (response && response.success) {
        assignments = response.assignments;
        renderAssignments();
      }
    });
  }

  function loadInitialData() {
    return $.when(
      window.apiRequest("GET", "/api/teachers"),
      window.apiRequest("GET", "/api/classes"),
      window.apiRequest("GET", "/api/subjects")
    ).done(function (teachersResp, classesResp, subjectsResp) {
      const teachersData = teachersResp[0];
      const classesData = classesResp[0];
      const subjectsData = subjectsResp[0];
      if (!teachersData.success || !classesData.success || !subjectsData.success) return;

      teachers = teachersData.teachers;
      classArms = classesData.arms.map(function (arm) {
        const level = classesData.levels.find(function (l) { return l.id === arm.levelId; });
        return {
          id: arm.id,
          levelId: arm.levelId,
          label: (level ? level.name : "") + " " + arm.name,
          isPrimary: !!(level && level.section === "primary"),
        };
      });
      levels = classesData.levels;
      subjects = subjectsData.subjects;

      populateTeacherPicker();
      populateSubjectPicker();

      // Deep-link support: /admin/assignments?teacherId=<id> from the
      // "Manage Assignments" row action on the teachers list.
      const params = new URLSearchParams(window.location.search);
      const preselect = params.get("teacherId");
      if (preselect && teachers.some(function (t) { return String(t.id) === preselect; })) {
        $teacherPicker.val(preselect).trigger("change");
      }
    });
  }

  $teacherPicker.on("change", function () {
    const teacherId = $(this).val();
    if (!teacherId) {
      selectedTeacherId = null;
      $builder.prop("hidden", true);
      $noTeacherState.show();
      return;
    }
    selectedTeacherId = Number(teacherId);
    $builder.prop("hidden", false);
    $noTeacherState.hide();
    loadAssignments();
    loadAvailability();
  });

  $subjectPicker.on("change", loadAvailability);

  $classGrid.on("change", ".js-class-box", function () {
    $(this).closest(".class-grid-item").toggleClass("is-checked", this.checked);
    updateAssignButton();
  });

  $classGrid.on("click", ".js-select-level", function () {
    const $boxes = $(this).closest(".class-grid-level").find(".js-class-box:not(:disabled)");
    $boxes.prop("checked", true).closest(".class-grid-item").addClass("is-checked");
    updateAssignButton();
  });

  const REASON_TEXT = {
    arm_not_found: "class not found",
    subject_not_found: "subject not found",
    primary_arm: "primary class",
    not_offered: "subject not offered",
    already_assigned: "already assigned",
    taken: "already taken"
  };

  $assignBtn.on("click", function () {
    if (!selectedTeacherId) return;
    const subjectId = Number($subjectPicker.val());
    const armIds = selectedArmIds();
    if (!subjectId || armIds.length === 0) return;

    $assignBtn.prop("disabled", true).find(".btn-spinner").show();

    window.apiRequest("POST", "/api/teachers/" + selectedTeacherId + "/assignments/bulk", {
      subjectIds: [subjectId],
      classArmIds: armIds
    })
      .done(function (response) {
        if (!response || !response.success) return;
        const created = response.created.length;
        const skipped = response.skipped || [];
        let message = created + (created === 1 ? " assignment added." : " assignments added.");
        if (skipped.length) {
          const reasons = skipped.slice(0, 4).map(function (item) {
            return (item.className || "Class") + ": " + (REASON_TEXT[item.reason] || item.reason) +
              (item.detail ? " (" + item.detail + ")" : "");
          });
          message += " Skipped " + skipped.length + ": " + reasons.join("; ") +
            (skipped.length > 4 ? "; and more." : ".");
        }
        window.showToast(message, created > 0 ? "success" : "danger");
        loadAssignments();
        loadAvailability();
      })
      .always(function () {
        $assignBtn.find(".btn-spinner").hide();
        updateAssignButton();
      });
  });

  $tbody.on("click", ".js-remove-assignment", function () {
    const id = Number($(this).closest("tr").data("id"));
    const assignment = assignments.find(function (a) { return a.id === id; });
    if (!assignment) return;

    window.confirmAction({
      title: "Remove assignment?",
      body: "This teacher will no longer be able to enter scores for " +
        (assignment.subjectName || "this subject") + " in " + (assignment.className || "this class") + ".",
      confirmLabel: "Remove",
      danger: true,
      onConfirm: function () {
        window.apiRequest("DELETE", "/api/teacher-assignments/" + id).done(function (response) {
          if (response && response.success) {
            loadAssignments();
            loadAvailability();
            window.showToast("Assignment removed.", "success");
          }
        });
      }
    });
  });

  // Point the admin at duplicate teachers or leftover assignments, if any.
  function loadIssuesBanner() {
    window.apiRequest("GET", "/api/assignments/conflicts").done(function (response) {
      if (!response || !response.success) return;
      const parts = [];
      if (response.orphans.length) {
        parts.push(response.orphans.length + " assignment(s) point to subjects a class no longer offers");
      }
      if (response.conflicts.length) {
        parts.push(response.conflicts.length + " class-subject(s) have more than one teacher");
      }
      const $banner = $("#assignmentIssuesBanner");
      if (parts.length === 0) {
        $banner.prop("hidden", true);
        return;
      }
      $banner.empty()
        .append($("<span>").text(parts.join(" and ") + ". "))
        .append($("<a>").attr("href", "/admin/class-assignments").text("Review on Class Assignments"))
        .prop("hidden", false);
    });
  }

  $noTeacherState.show();
  $builder.prop("hidden", true);
  loadInitialData();
  loadIssuesBanner();
});
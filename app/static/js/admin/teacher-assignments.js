/* ==========================================================================
   teacher-assignments.js — Teacher -> Class + Subject assignment, wired to
   the real API. Structural pattern follows class-subjects.js.
   ========================================================================== */

$(function () {
  const $teacherPicker = $("#teacherPicker");
  const $builder = $("#assignmentBuilder");
  const $noTeacherState = $("#noTeacherSelectedState");
  const $classArmPicker = $("#classArmPicker");
  const $subjectPicker = $("#subjectPicker");
  const $addBtn = $("#addAssignmentBtn");
  const $tbody = $("#assignmentsTableBody");
  const $table = $("#assignmentsTable").closest(".table-wrapper");
  const $empty = $("#assignmentsEmptyState");

  let teachers = [];
  let classArms = []; // [{id, label}]
  let subjects = [];  // [{id, name, code}]
  let assignments = [];
  let selectedTeacherId = null;

  function populateTeacherPicker() {
    $teacherPicker.empty().append('<option value="">Choose a teacher&hellip;</option>');
    teachers.forEach(function (t) {
      $teacherPicker.append('<option value="' + t.id + '">' + t.fullName + " (" + t.email + ")</option>");
    });
  }

  function populateClassAndSubjectPickers() {
    $classArmPicker.empty();
    classArms.forEach(function (arm) {
      $classArmPicker.append('<option value="' + arm.id + '">' + arm.label + "</option>");
    });
    $subjectPicker.empty();
    subjects.forEach(function (s) {
      $subjectPicker.append('<option value="' + s.id + '">' + s.name + "</option>");
    });
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
      const $row = $(
        '<tr data-id="' + a.id + '">' +
          "<td>" + $("<div>").text(a.className || "").html() + "</td>" +
          "<td>" + $("<div>").text(a.subjectName || "").html() + "</td>" +
          '<td class="row-actions">' +
            '<button type="button" class="btn btn-outline-danger btn-sm js-remove-assignment"><i class="bi bi-trash"></i></button>' +
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
        return { id: arm.id, label: (level ? level.name : "") + " " + arm.name };
      });
      subjects = subjectsData.subjects;

      populateTeacherPicker();
      populateClassAndSubjectPickers();

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
  });

  $addBtn.on("click", function () {
    if (!selectedTeacherId) return;
    const classArmId = Number($classArmPicker.val());
    const subjectId = Number($subjectPicker.val());
    if (!classArmId || !subjectId) return;

    $addBtn.prop("disabled", true).find(".btn-spinner").show();

    window.apiRequest("POST", "/api/teachers/" + selectedTeacherId + "/assignments", {
      classArmId: classArmId,
      subjectId: subjectId,
    })
      .done(function (response) {
        if (response && response.success) {
          loadAssignments();
          window.showToast("Assignment added.", "success");
        }
      })
      .always(function () {
        $addBtn.prop("disabled", false).find(".btn-spinner").hide();
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
            window.showToast("Assignment removed.", "success");
          }
        });
      }
    });
  });

  $noTeacherState.show();
  $builder.prop("hidden", true);
  loadInitialData();
});
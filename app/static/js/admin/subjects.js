/* ==========================================================================
   subjects.js — Subjects CRUD, wired to the real API.
   ========================================================================== */

$(function () {
  let subjects = [];

  const $tbody = $("#subjectsTableBody");
  const $empty = $("#subjectsEmptyState");
  const $table = $("#subjectsTable").closest(".table-wrapper");
  const $modal = $("#subjectModal");
  const $form = $("#subjectForm");
  const $saveBtn = $("#subjectSaveBtn");

  function render() {
    $tbody.empty();
    if (subjects.length === 0) {
      $table.hide();
      $empty.prop("hidden", false);
      return;
    }
    $table.show();
    $empty.prop("hidden", true);

    subjects.forEach(function (s) {
      const $row = $(
        '<tr data-id="' + s.id + '">' +
          "<td>" + $("<div>").text(s.name).html() + "</td>" +
          "<td>" + $("<div>").text(s.code || "").html() + "</td>" +
          '<td class="row-actions">' +
            '<button type="button" class="btn btn-secondary btn-sm js-edit-subject"><i class="bi bi-pencil"></i></button>' +
            '<button type="button" class="btn btn-outline-danger btn-sm js-delete-subject"><i class="bi bi-trash"></i></button>' +
          "</td>" +
        "</tr>"
      );
      $tbody.append($row);
    });
  }

  function loadSubjects() {
    window.apiRequest("GET", "/api/subjects").done(function (response) {
      if (response && response.success) {
        subjects = response.subjects;
        render();
      }
    });
  }

  function openForAdd() {
    $("#subjectModalTitle").text("Add Subject");
    $("#subjectId").val("");
    $("#subjectName").val("");
    $("#subjectCode").val("");
    window.openModal($modal);
  }

  function openForEdit(subject) {
    $("#subjectModalTitle").text("Edit Subject");
    $("#subjectId").val(subject.id);
    $("#subjectName").val(subject.name);
    $("#subjectCode").val(subject.code || "");
    window.openModal($modal);
  }

  $("#addSubjectBtn").on("click", openForAdd);

  $(document).on("click", ".js-edit-subject", function () {
    const id = Number($(this).closest("tr").data("id"));
    const subject = subjects.find(function (s) { return s.id === id; });
    if (subject) openForEdit(subject);
  });

  $(document).on("click", ".js-delete-subject", function () {
    const id = Number($(this).closest("tr").data("id"));
    const subject = subjects.find(function (s) { return s.id === id; });
    if (!subject) return;

    window.confirmAction({
      title: "Delete subject?",
      body: 'This will permanently remove "' + subject.name + '". This cannot be undone.',
      confirmLabel: "Delete",
      danger: true,
      onConfirm: function () {
        window.apiRequest("DELETE", "/api/subjects/" + id).done(function (response) {
          if (response && response.success) {
            loadSubjects();
            window.showToast("Subject deleted.", "success");
          }
        });
      }
    });
  });

  $form.on("submit", function (e) {
    e.preventDefault();

    const id = $("#subjectId").val();
    const name = $("#subjectName").val().trim();
    const code = $("#subjectCode").val().trim();
    if (!name || !code) return;

    $saveBtn.prop("disabled", true).find(".btn-spinner").show();

    const request = id
      ? window.apiRequest("PUT", "/api/subjects/" + id, { name: name, code: code })
      : window.apiRequest("POST", "/api/subjects", { name: name, code: code });

    request
      .done(function (response) {
        if (response && response.success) {
          loadSubjects();
          window.showToast(id ? "Subject updated." : "Subject added.", "success");
          window.closeModal($modal);
        }
      })
      .always(function () {
        $saveBtn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  loadSubjects();
});

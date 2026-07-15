/* ==========================================================================
   teachers.js — Teacher CRUD, wired to the real API.
   ========================================================================== */

$(function () {
  const tableBody = document.getElementById("teachersTableBody");
  if (!tableBody) return; // this page isn't loaded

  let teachers = [];

  const $tbody = $("#teachersTableBody");
  const $empty = $("#teachersEmptyState");
  const $table = $("#teachersTable").closest(".table-wrapper");
  const $modal = $("#teacherModal");
  const $form = $("#teacherForm");
  const $saveBtn = $("#teacherSaveBtn");
  const $searchInput = $("#teacherSearchInput");
  const $filterStatus = $("#filterStatus");
  const $clearFiltersBtn = $("#clearFiltersBtn");
  const $genPasswordModal = $("#generatedPasswordModal");

  function initials(name) {
    const parts = name.trim().split(/\s+/);
    return ((parts[0] || "")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }

  function getFiltered() {
    const q = $searchInput.val().trim().toLowerCase();
    const status = $filterStatus.val();

    return teachers.filter(function (t) {
      const matchesQuery = !q ||
        t.fullName.toLowerCase().includes(q) ||
        t.email.toLowerCase().includes(q);
      const matchesStatus = !status || (status === "active" ? t.isActive : !t.isActive);
      return matchesQuery && matchesStatus;
    });
  }

  function render() {
    const filtered = getFiltered();
    $tbody.empty();

    if (filtered.length === 0) {
      $table.hide();
      $empty.show();
      return;
    }
    $table.show();
    $empty.hide();

    const rowTemplate = document.getElementById("teacherRowTemplate");

    filtered.forEach(function (t) {
      const row = rowTemplate.content.firstElementChild.cloneNode(true);
      row.dataset.teacherId = t.id;
      row.querySelector(".avatar-initial").textContent = initials(t.fullName);
      row.querySelector(".teacher-name-cell").textContent = t.fullName;
      row.querySelector(".teacher-email-cell").textContent = t.email;
      row.querySelector(".teacher-assignment-count-cell").textContent = t.assignmentCount;

      const badge = row.querySelector(".teacher-status-badge");
      if (t.isActive) {
        badge.textContent = "Active";
        badge.classList.add("badge-success");
      } else {
        badge.textContent = "Inactive";
        badge.classList.add("badge-neutral");
      }

      row.querySelector(".js-manage-assignments").href = "/admin/assignments?teacherId=" + t.id;

      row.querySelector(".js-edit-teacher").addEventListener("click", function () {
        closeAllDropdowns();
        openForEdit(t);
      });

      row.querySelector(".js-reset-password").addEventListener("click", function () {
        closeAllDropdowns();
        window.confirmAction({
          title: "Reset password?",
          body: "A new password will be generated for " + t.fullName + ". The previous password will stop working.",
          confirmLabel: "Reset Password",
          onConfirm: function () {
            window.apiRequest("POST", "/api/teachers/" + t.id + "/reset-password").done(function (response) {
              if (response && response.success) {
                showGeneratedPassword(response.generatedPassword);
              }
            });
          }
        });
      });

      row.querySelector(".js-deactivate-teacher").addEventListener("click", function () {
        closeAllDropdowns();
        const willDeactivate = t.isActive;
        window.confirmAction({
          title: willDeactivate ? "Deactivate teacher?" : "Reactivate teacher?",
          body: t.fullName + " will " + (willDeactivate ? "lose portal access." : "regain portal access."),
          confirmLabel: willDeactivate ? "Deactivate" : "Reactivate",
          danger: willDeactivate,
          onConfirm: function () {
            window.apiRequest("POST", "/api/teachers/" + t.id + "/deactivate", { isActive: !willDeactivate })
              .done(function (response) {
                if (response && response.success) {
                  loadTeachers();
                  window.showToast(t.fullName + (willDeactivate ? " deactivated." : " reactivated."), "success");
                }
              });
          }
        });
      });

      $tbody.append(row);
    });
  }

  function closeAllDropdowns() {
    document.querySelectorAll(".row-actions-dropdown.show").forEach(function (el) {
      el.classList.remove("show");
    });
  }

  $tbody.on("click", function (e) {
    const trigger = e.target.closest(".row-actions-trigger");
    if (!trigger) return;
    const dropdown = trigger.nextElementSibling;
    const wasOpen = dropdown.classList.contains("show");
    closeAllDropdowns();
    if (!wasOpen) dropdown.classList.add("show");
  });

  $(document).on("click", function (e) {
    if (!e.target.closest(".row-actions-menu")) closeAllDropdowns();
  });

  function loadTeachers() {
    window.apiRequest("GET", "/api/teachers").done(function (response) {
      if (response && response.success) {
        teachers = response.teachers;
        render();
      }
    });
  }

  function openForAdd() {
    $("#teacherModalTitle").text("Add Teacher");
    $form[0].reset();
    $("#teacherId").val("");
    window.openModal($modal);
  }

  function openForEdit(teacher) {
    $("#teacherModalTitle").text("Edit Teacher");
    $("#teacherId").val(teacher.id);
    $("#teacherFullName").val(teacher.fullName);
    $("#teacherEmail").val(teacher.email);
    window.openModal($modal);
  }

  function showGeneratedPassword(password) {
    $("#generatedPasswordDisplay").val(password);
    window.openModal($genPasswordModal);
  }

  $("#addTeacherBtn").on("click", openForAdd);

  $form.on("submit", function (e) {
    e.preventDefault();

    const id = $("#teacherId").val();
    const payload = {
      fullName: $("#teacherFullName").val().trim(),
      email: $("#teacherEmail").val().trim(),
    };
    if (!payload.fullName || !payload.email) return;

    $saveBtn.prop("disabled", true).find(".btn-spinner").show();

    const request = id
      ? window.apiRequest("PUT", "/api/teachers/" + id, payload)
      : window.apiRequest("POST", "/api/teachers", payload);

    request
      .done(function (response) {
        if (response && response.success) {
          loadTeachers();
          window.closeModal($modal);
          if (response.teacher && response.teacher.generatedPassword) {
            showGeneratedPassword(response.teacher.generatedPassword);
          } else {
            window.showToast(id ? "Teacher updated." : "Teacher added.", "success");
          }
        }
      })
      .always(function () {
        $saveBtn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  let debounceTimer;
  $searchInput.on("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(render, 200);
  });
  $filterStatus.on("change", render);
  $clearFiltersBtn.on("click", function () {
    $searchInput.val("");
    $filterStatus.val("");
    render();
  });

  loadTeachers();
});
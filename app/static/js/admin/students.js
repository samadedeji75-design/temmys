/* ==========================================================================
   students.js — Student CRUD, wired to the real API.
   ========================================================================== */

$(function () {
  const tableBody = document.getElementById("studentsTableBody");
  if (!tableBody) return; // this page isn't loaded

  let students = [];
  let classArms = []; // [{id, label}]

  const $tbody = $("#studentsTableBody");
  const $empty = $("#studentsEmptyState");
  const $table = $("#studentsTable").closest(".table-wrapper");
  const $modal = $("#studentModal");
  const $form = $("#studentForm");
  const $saveBtn = $("#studentSaveBtn");
  const $searchInput = $("#studentSearchInput");
  const $filterClassArm = $("#filterClassArm");
  const $filterStatus = $("#filterStatus");
  const $clearFiltersBtn = $("#clearFiltersBtn");
  const $genPasswordModal = $("#generatedPasswordModal");
  const $moreDetailsSection = $("#moreDetailsSection");
  const $passwordManageModal = $("#passwordManageModal");
  let currentPasswordManageStudent = null;

  function initials(name) {
    const parts = name.trim().split(/\s+/);
    return ((parts[0] || "")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }

  function getFiltered() {
    const q = $searchInput.val().trim().toLowerCase();
    const classArmId = $filterClassArm.val();
    const status = $filterStatus.val();

    return students.filter(function (s) {
      const matchesQuery = !q ||
        s.fullName.toLowerCase().includes(q) ||
        s.admissionNumber.toLowerCase().includes(q);
      const matchesClass = !classArmId || String(s.classArmId) === classArmId;
      const matchesStatus = !status || (status === "active" ? s.isActive : !s.isActive);
      return matchesQuery && matchesClass && matchesStatus;
    });
  }

  function render() {
    const filtered = getFiltered();
    $tbody.empty();

    if (filtered.length === 0) {
      $table.hide();
      $empty.prop("hidden", false);
      return;
    }
    $table.show();
    $empty.prop("hidden", true);

    const rowTemplate = document.getElementById("studentRowTemplate");

    filtered.forEach(function (s) {
      const row = rowTemplate.content.firstElementChild.cloneNode(true);
      row.dataset.studentId = s.id;
      row.querySelector(".avatar-initial").textContent = initials(s.fullName);
      row.querySelector(".student-name-cell").textContent = s.fullName;
      row.querySelector(".student-admission-cell").textContent = s.admissionNumber;
      row.querySelector(".student-class-cell").textContent = s.className || "—";
      row.querySelector(".student-gender-cell").textContent = s.gender || "—";
      row.querySelector(".student-guardian-cell").textContent = s.guardianPhone || "—";

      const badge = row.querySelector(".student-status-badge");
      if (s.isActive) {
        badge.textContent = "Active";
        badge.classList.add("badge-success");
      } else {
        badge.textContent = "Inactive";
        badge.classList.add("badge-neutral");
      }

      row.querySelector(".js-edit-student").addEventListener("click", function () {
        closeAllDropdowns();
        openForEdit(s);
      });

      row.querySelector(".js-reset-password").addEventListener("click", function () {
        closeAllDropdowns();
        window.confirmAction({
          title: "Reset password?",
          body: "A new password will be generated for " + s.fullName + ". The previous password will stop working.",
          confirmLabel: "Reset Password",
          onConfirm: function () {
            window.apiRequest("POST", "/api/students/" + s.id + "/reset-password").done(function (response) {
              if (response && response.success) {
                showGeneratedPassword(response.generatedPassword);
              }
            });
          }
        });
      });

      row.querySelector(".js-manage-password").addEventListener("click", function () {
        closeAllDropdowns();
        openPasswordManager(s);
      });

      row.querySelector(".js-deactivate-student").addEventListener("click", function () {
        closeAllDropdowns();
        const willDeactivate = s.isActive;
        window.confirmAction({
          title: willDeactivate ? "Deactivate student?" : "Reactivate student?",
          body: s.fullName + " (" + s.admissionNumber + ") will " +
            (willDeactivate ? "lose portal access." : "regain portal access."),
          confirmLabel: willDeactivate ? "Deactivate" : "Reactivate",
          danger: willDeactivate,
          onConfirm: function () {
            window.apiRequest("POST", "/api/students/" + s.id + "/deactivate", { isActive: !willDeactivate })
              .done(function (response) {
                if (response && response.success) {
                  loadStudents();
                  window.showToast(s.fullName + (willDeactivate ? " deactivated." : " reactivated."), "success");
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

  function populateClassPickers() {
    $filterClassArm.find("option:not(:first)").remove();
    $("#studentClassArm").empty();
    classArms.forEach(function (arm) {
      $filterClassArm.append('<option value="' + arm.id + '">' + arm.label + "</option>");
      $("#studentClassArm").append('<option value="' + arm.id + '">' + arm.label + "</option>");
    });
  }

  function loadClasses() {
    return window.apiRequest("GET", "/api/classes").done(function (response) {
      if (!response || !response.success) return;
      classArms = response.arms.map(function (arm) {
        const level = response.levels.find(function (l) { return l.id === arm.levelId; });
        return { id: arm.id, label: (level ? level.name : "") + " " + arm.name };
      });
      populateClassPickers();
    });
  }

  function loadStudents() {
    window.apiRequest("GET", "/api/students").done(function (response) {
      if (response && response.success) {
        students = response.students;
        render();
      }
    });
  }

  function openForAdd() {
    $("#studentModalTitle").text("Add Student");
    $form[0].reset();
    $("#studentId").val("");
    $moreDetailsSection.prop("hidden", true);
    window.openModal($modal);
  }

  function openForEdit(student) {
    $("#studentModalTitle").text("Edit Student");
    $("#studentId").val(student.id);
    $("#admissionNumber").val(student.admissionNumber).prop("disabled", true);
    $("#studentFullName").val(student.fullName);
    $("#studentClassArm").val(student.classArmId);
    $("#studentGender").val(student.gender || "");
    $("#studentDob").val(student.dateOfBirth || "");
    $("#guardianName").val(student.guardianName || "");
    $("#guardianPhone").val(student.guardianPhone || "");
    $("#guardianEmail").val(student.guardianEmail || "");
    $moreDetailsSection.prop("hidden", true);
    window.openModal($modal);
  }

  $("#toggleMoreDetails").on("click", function () {
    $moreDetailsSection.prop("hidden", !$moreDetailsSection.prop("hidden"));
  });

  function showGeneratedPassword(password) {
    $("#generatedPasswordDisplay").val(password);
    window.openModal($genPasswordModal);
  }

  function openPasswordManager(student) {
    currentPasswordManageStudent = student;
    $("#passwordManageTitle").text("Manage Password — " + student.fullName);
    $("#newPasswordInput").val("");
    $("#currentPasswordDisplay").val("").data("plain", "").data("masked", false);
    $("#togglePasswordVisibility").prop("disabled", false);
    $("#passwordUnavailableHint").prop("hidden", true);

    window.apiRequest("GET", "/api/students/" + student.id + "/password").done(function (response) {
      if (!response || !response.success) return;
      if (response.password === null || response.password === undefined) {
        $("#passwordUnavailableHint").prop("hidden", false);
        $("#togglePasswordVisibility").prop("disabled", true);
        $("#currentPasswordDisplay").val("");
        return;
      }
      $("#currentPasswordDisplay").data("plain", response.password).val("••••••••").data("masked", true);
    });

    window.openModal($passwordManageModal);
  }

  $("#togglePasswordVisibility").on("click", function () {
    const $display = $("#currentPasswordDisplay");
    const masked = $display.data("masked");
    const plain = $display.data("plain") || "";
    if (!plain) return;
    if (masked) {
      $display.val(plain).data("masked", false);
      $(this).find("i").removeClass("bi-eye").addClass("bi-eye-slash");
    } else {
      $display.val("••••••••").data("masked", true);
      $(this).find("i").removeClass("bi-eye-slash").addClass("bi-eye");
    }
  });

  $("#generateNewPasswordBtn").on("click", function () {
    $("#newPasswordInput").val(crypto.randomUUID().slice(0, 10));
  });

  $("#savePasswordBtn").on("click", function () {
    if (!currentPasswordManageStudent) return;
    const newPassword = $("#newPasswordInput").val();
    window.apiRequest("PUT", "/api/students/" + currentPasswordManageStudent.id + "/password", { password: newPassword })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Password updated.", "success");
          window.closeModal($passwordManageModal);
        }
      });
  });

  $("#addStudentBtn").on("click", function () {
    $("#admissionNumber").prop("disabled", false);
    openForAdd();
  });

  $form.on("submit", function (e) {
    e.preventDefault();

    const id = $("#studentId").val();
    const payload = {
      admissionNumber: $("#admissionNumber").val().trim(),
      fullName: $("#studentFullName").val().trim(),
      classArmId: Number($("#studentClassArm").val()),
      gender: $("#studentGender").val(),
      dateOfBirth: $("#studentDob").val(),
      guardianName: $("#guardianName").val().trim(),
      guardianPhone: $("#guardianPhone").val().trim(),
      guardianEmail: $("#guardianEmail").val().trim(),
    };

    if (!payload.fullName || !payload.classArmId) return;

    $saveBtn.prop("disabled", true).find(".btn-spinner").show();

    const request = id
      ? window.apiRequest("PUT", "/api/students/" + id, payload)
      : window.apiRequest("POST", "/api/students", payload);

    request
      .done(function (response) {
        if (response && response.success) {
          loadStudents();
          window.closeModal($modal);
          if (response.student && response.student.generatedPassword) {
            showGeneratedPassword(response.student.generatedPassword);
          } else {
            window.showToast(id ? "Student updated." : "Student added.", "success");
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
  $filterClassArm.on("change", render);
  $filterStatus.on("change", render);
  $clearFiltersBtn.on("click", function () {
    $searchInput.val("");
    $filterClassArm.val("");
    $filterStatus.val("");
    render();
  });

  $.when(loadClasses()).done(loadStudents);
});
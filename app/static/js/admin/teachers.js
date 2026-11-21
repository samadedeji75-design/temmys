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
  const $passwordManageModal = $("#passwordManageModal");
  let currentPasswordManageTeacher = null;

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
      const $placeholderBadge = $(row).find(".teacher-email-placeholder-badge");
      $placeholderBadge.prop("hidden", !t.emailIsPlaceholder);
      row.querySelector(".teacher-assignment-count").textContent = t.assignmentCount;
      const classTeacherOf = t.classTeacherOf || [];
      const $classTeacherOf = $(row).find(".teacher-class-teacher-of");
      if (classTeacherOf.length > 0) {
        $classTeacherOf.text("Class teacher: " + classTeacherOf.join(", ")).prop("hidden", false);
      }

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

      row.querySelector(".js-manage-password").addEventListener("click", function () {
        closeAllDropdowns();
        openPasswordManager(t);
      });

      row.querySelector(".js-send-credentials-email").addEventListener("click", function () {
        closeAllDropdowns();
        if (t.emailIsPlaceholder) {
          window.showToast("This teacher doesn't have a real email yet — edit their profile first.", "error");
          return;
        }
        window.confirmAction({
          title: "Send credentials email?",
          body: "This will email " + t.fullName + " (" + t.email + ") their login details and current class/subject assignments.",
          confirmLabel: "Send Email",
          onConfirm: function () {
            window.apiRequest("POST", "/api/teachers/" + t.id + "/send-credentials-email")
              .done(function (response) {
                if (response && response.success) {
                  window.showToast(response.message || "Credentials email sent.", "success");
                } else {
                  window.showToast((response && response.message) || "Could not send email.", "error");
                }
              })
              .fail(function (xhr) {
                const message = (xhr.responseJSON && xhr.responseJSON.message) || "Could not send email.";
                window.showToast(message, "error");
              });
          }
        });
      });

      row.querySelector(".js-transfer-teacher").addEventListener("click", function () {
        closeAllDropdowns();
        openTransfer(t);
      });

      row.querySelector(".js-clear-teacher").addEventListener("click", function () {
        closeAllDropdowns();
        clearTeacher(t);
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
                  if (willDeactivate && response.hasAssignments) {
                    // Deactivating never clears assignments; offer the hand over.
                    setTimeout(function () {
                      window.confirmAction({
                        title: "Transfer assignments?",
                        body: "This teacher still has assignments. Transfer them now?",
                        confirmLabel: "Transfer now",
                        onConfirm: function () { openTransfer(t); }
                      });
                    }, 250);
                  }
                }
              });
          }
        });
      });

      $tbody.append(row);
    });
  }

  /* ---------------- Transfer and clear assignments ---------------- */

  const $transferModal = $("#transferModal");
  const $transferSelect = $("#transferTargetSelect");
  let transferSource = null;

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  function updateTransferSummary() {
    if (!transferSource) return;
    const targetId = Number($transferSelect.val());
    const target = teachers.find(function (x) { return x.id === targetId; });
    const roles = (transferSource.classTeacherOf || []).length;
    $("#transferSummary").text(
      "Move " + plural(transferSource.manualAssignmentCount || 0, "subject assignment", "subject assignments") +
      " and " + plural(roles, "class teacher role", "class teacher roles") +
      " from " + transferSource.fullName + " to " + (target ? target.fullName : "the chosen teacher") + "."
    );
  }

  function openTransfer(teacher) {
    transferSource = teacher;
    $("#transferModalTitle").text("Transfer assignments from " + teacher.fullName);
    $transferSelect.empty();
    const others = teachers.filter(function (x) { return x.isActive && x.id !== teacher.id; });
    others.forEach(function (x) {
      $transferSelect.append($("<option>").val(x.id).text(x.fullName));
    });
    if (others.length === 0) {
      window.showToast("There is no other active teacher to transfer to.", "danger");
      return;
    }
    updateTransferSummary();
    window.openModal($transferModal);
  }

  $transferSelect.on("change", updateTransferSummary);

  $("#transferConfirmBtn").on("click", function () {
    if (!transferSource) return;
    const source = transferSource;
    const targetId = Number($transferSelect.val());
    const target = teachers.find(function (x) { return x.id === targetId; });
    if (!target) return;
    window.closeModal($transferModal);
    window.confirmAction({
      title: "Transfer assignments?",
      body: $("#transferSummary").text() + " " + source.fullName + " will lose access to enter those scores.",
      confirmLabel: "Transfer",
      danger: true,
      onConfirm: function () {
        window.apiRequest("POST", "/api/teachers/" + source.id + "/transfer-assignments", { toTeacherId: target.id })
          .done(function (response) {
            if (response && response.success) {
              loadTeachers();
              let message = "Moved " + plural(response.movedAssignments, "assignment", "assignments") +
                " and " + plural(response.movedClassTeacherRoles, "class teacher role", "class teacher roles") + ".";
              if (response.skippedDuplicates) {
                message += " " + plural(response.skippedDuplicates, "duplicate was", "duplicates were") + " skipped.";
              }
              window.showToast(message, "success");
            }
          });
      }
    });
  });

  function clearTeacher(teacher) {
    window.apiRequest("POST", "/api/teachers/" + teacher.id + "/clear-assignments", {})
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status !== 409 || data.code !== "confirm_clear") return;
        const roles = data.classTeacherOf || [];
        if (!data.manualCount && roles.length === 0) {
          window.showToast("Nothing to clear.", "success");
          return;
        }
        window.confirmAction({
          title: "Clear assignments for " + teacher.fullName + "?",
          body: "This removes " + plural(data.manualCount, "subject assignment", "subject assignments") +
            (roles.length ? " and the class teacher role for " + roles.join(", ") +
              " (including the subjects it gave them)" : "") +
            ". Scores already entered are kept.",
          confirmLabel: "Clear assignments",
          danger: true,
          onConfirm: function () {
            window.apiRequest("POST", "/api/teachers/" + teacher.id + "/clear-assignments", { confirm: true })
              .done(function (response) {
                if (response && response.success) {
                  loadTeachers();
                  window.showToast("Assignments cleared.", "success");
                }
              });
          }
        });
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

  function openPasswordManager(teacher) {
    currentPasswordManageTeacher = teacher;
    $("#passwordManageTitle").text("Manage Password — " + teacher.fullName);
    $("#newPasswordInput").val("");
    $("#currentPasswordDisplay").val("").data("plain", "").data("masked", false);
    $("#togglePasswordVisibility").prop("disabled", false);
    $("#passwordUnavailableHint").prop("hidden", true);

    window.apiRequest("GET", "/api/teachers/" + teacher.id + "/password").done(function (response) {
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
    if (!currentPasswordManageTeacher) return;
    const newPassword = $("#newPasswordInput").val();
    window.apiRequest("PUT", "/api/teachers/" + currentPasswordManageTeacher.id + "/password", { password: newPassword })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Password updated.", "success");
          window.closeModal($passwordManageModal);
        }
      });
  });

  $("#addTeacherBtn").on("click", openForAdd);

  $form.on("submit", function (e) {
    e.preventDefault();

    const id = $("#teacherId").val();
    const payload = {
      fullName: $("#teacherFullName").val().trim(),
      email: $("#teacherEmail").val().trim(),
    };
    if (!payload.fullName) return;

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
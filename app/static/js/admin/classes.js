/* ==========================================================================
   classes.js: Levels/Arms CRUD, sections, class teacher and clearing
   assignments, wired to the real API.
   ========================================================================== */

$(function () {
  let levels = [];
  let arms = [];
  let teachers = [];

  const $groups = $("#classesGroups");
  const $empty = $("#classesEmptyState");

  function esc(text) {
    return $("<div>").text(text == null ? "" : text).html();
  }

  function levelById(id) {
    return levels.find(function (l) { return l.id === id; });
  }

  function armLabel(arm) {
    const level = levelById(arm.levelId);
    return (level ? level.name : "") + " " + arm.name;
  }

  function render() {
    $groups.empty();
    if (levels.length === 0) {
      $empty.prop("hidden", false);
      return;
    }
    $empty.prop("hidden", true);

    levels.forEach(function (level) {
      const levelArms = arms.filter(function (a) { return a.levelId === level.id; });
      const isPrimary = level.section === "primary";
      const $card = $('<div class="card mb-4" data-level-id="' + level.id + '">' +
        '<div class="card-header d-flex justify-between align-center">' +
          '<h2></h2>' +
          '<div class="d-flex gap-2 align-center">' +
            '<span class="badge"></span>' +
            '<button type="button" class="btn btn-secondary btn-sm js-edit-level"><i class="bi bi-pencil"></i> Edit level</button>' +
          '</div>' +
        '</div>' +
        '<div class="table-wrapper"><table class="data-table"><thead><tr>' +
        '<th>Arm</th><th>Class teacher</th><th>Students</th><th></th></tr></thead><tbody></tbody></table></div></div>');

      $card.find(".card-header h2").text(level.name);
      $card.find(".badge")
        .addClass(isPrimary ? "badge-info" : "badge-neutral")
        .text(isPrimary ? "Primary" : "Secondary");
      const $tbody = $card.find("tbody");

      if (levelArms.length === 0) {
        $tbody.append('<tr><td colspan="4" class="cell-muted">No arms yet for this level.</td></tr>');
      } else {
        levelArms.forEach(function (arm) {
          const teacherCell = arm.classTeacherName
            ? esc(arm.classTeacherName)
            : '<span class="cell-muted">No class teacher</span>';
          const $row = $(
            '<tr data-id="' + arm.id + '">' +
              "<td>" + esc(level.name) + " " + esc(arm.name) + "</td>" +
              "<td>" + teacherCell + "</td>" +
              '<td class="cell-numeric">' + arm.studentCount + "</td>" +
              '<td class="row-actions">' +
                '<button type="button" class="btn btn-secondary btn-sm js-class-teacher" title="Set class teacher"><i class="bi bi-person-badge"></i> Class teacher</button>' +
                '<button type="button" class="btn btn-secondary btn-sm js-clear-arm" title="Clear assignments"><i class="bi bi-eraser"></i></button>' +
                '<button type="button" class="btn btn-secondary btn-sm js-edit-arm" title="Edit"><i class="bi bi-pencil"></i></button>' +
                '<button type="button" class="btn btn-outline-danger btn-sm js-delete-arm" title="Delete"><i class="bi bi-trash"></i></button>' +
              "</td>" +
            "</tr>"
          );
          $tbody.append($row);
        });
      }
      $groups.append($card);
    });
  }

  function populateLevelSelect() {
    const $select = $("#armLevel").empty();
    levels.forEach(function (l) {
      $select.append($("<option>").val(l.id).text(l.name));
    });
  }

  function loadClasses() {
    window.apiRequest("GET", "/api/classes").done(function (response) {
      if (response && response.success) {
        levels = response.levels;
        arms = response.arms;
        render();
      }
    });
  }

  function loadTeachers() {
    window.apiRequest("GET", "/api/teachers").done(function (response) {
      if (response && response.success) {
        teachers = response.teachers.filter(function (t) { return t.isActive; });
      }
    });
  }

  function describeReplaces(replaces) {
    if (!replaces || replaces.length === 0) return "";
    return replaces.map(function (r) {
      return r.teacherName + " (" + r.subjectCount + (r.subjectCount === 1 ? " subject" : " subjects") + ")";
    }).join(", ");
  }

  /* ---------------- Levels ---------------- */

  $("#addLevelBtn").on("click", function () {
    $("#levelModalTitle").text("Add Level");
    $("#levelId").val("");
    $("#levelName").val("");
    $("#levelSection").val("secondary");
    window.openModal($("#levelModal"));
  });

  $(document).on("click", ".js-edit-level", function () {
    const id = Number($(this).closest(".card").data("level-id"));
    const level = levelById(id);
    if (!level) return;
    $("#levelModalTitle").text("Edit Level");
    $("#levelId").val(level.id);
    $("#levelName").val(level.name);
    $("#levelSection").val(level.section || "secondary");
    window.openModal($("#levelModal"));
  });

  $("#levelForm").on("submit", function (e) {
    e.preventDefault();
    const id = $("#levelId").val();
    const name = $("#levelName").val().trim();
    const section = $("#levelSection").val();
    if (!name) return;

    const $btn = $("#levelSaveBtn");
    $btn.prop("disabled", true).find(".btn-spinner").show();

    saveLevel(id, { name: name, section: section }, $btn);
  });

  function saveLevel(id, body, $btn) {
    const request = id
      ? window.apiRequest("PUT", "/api/classes/levels/" + id, body)
      : window.apiRequest("POST", "/api/classes/levels", body);

    request
      .done(function (response) {
        if (response && response.success) {
          loadClasses();
          window.closeModal($("#levelModal"));
          window.showToast(id ? "Level updated." : "Level added.", "success");
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status === 409 && data.code === "confirm_replace") {
          const who = describeReplaces(data.replaces);
          window.confirmAction({
            title: "Make this level primary?",
            body: "Each class with a class teacher will give that teacher every subject. This replaces: " +
              who + ". Scores already entered are kept.",
            confirmLabel: "Make primary",
            danger: true,
            onConfirm: function () {
              saveLevel(id, Object.assign({}, body, { confirmReplace: true }), $btn);
            }
          });
        }
      })
      .always(function () {
        $btn.prop("disabled", false).find(".btn-spinner").hide();
      });
  }

  /* ---------------- Arms ---------------- */

  $("#addArmBtn").on("click", function () {
    $("#armModalTitle").text("Add Arm");
    $("#armId, #armName").val("");
    populateLevelSelect();
    window.openModal($("#armModal"));
  });

  $(document).on("click", ".js-edit-arm", function () {
    const id = Number($(this).closest("tr").data("id"));
    const arm = arms.find(function (a) { return a.id === id; });
    if (!arm) return;
    $("#armModalTitle").text("Edit Arm");
    populateLevelSelect();
    $("#armId").val(arm.id);
    $("#armLevel").val(arm.levelId);
    $("#armName").val(arm.name);
    window.openModal($("#armModal"));
  });

  $(document).on("click", ".js-delete-arm", function () {
    const id = Number($(this).closest("tr").data("id"));
    const arm = arms.find(function (a) { return a.id === id; });
    if (!arm) return;

    window.confirmAction({
      title: "Delete arm?",
      body: "This will permanently remove this arm and its teacher assignments. Students in it will need reassigning first.",
      confirmLabel: "Delete",
      danger: true,
      onConfirm: function () {
        window.apiRequest("DELETE", "/api/classes/arms/" + id).done(function (response) {
          if (response && response.success) {
            loadClasses();
            window.showToast("Arm deleted.", "success");
          }
        });
      }
    });
  });

  function saveArm(id, payload, $btn) {
    const request = id
      ? window.apiRequest("PUT", "/api/classes/arms/" + id, payload)
      : window.apiRequest("POST", "/api/classes/arms", payload);

    request
      .done(function (response) {
        if (response && response.success) {
          loadClasses();
          window.showToast(id ? "Arm updated." : "Arm added.", "success");
          window.closeModal($("#armModal"));
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status === 409 && data.code === "has_assignments") {
          const who = describeReplaces(data.replaces);
          window.confirmAction({
            title: "Move this class?",
            body: "Moving this class to a different section removes its teacher assignments" +
              (who ? " (" + who + ")" : "") +
              (data.hasClassTeacher ? " and its class teacher" : "") +
              ". Scores already entered are kept.",
            confirmLabel: "Move and clear",
            danger: true,
            onConfirm: function () {
              saveArm(id, Object.assign({}, payload, { clearAssignments: true }), $btn);
            }
          });
        }
      })
      .always(function () {
        $btn.prop("disabled", false).find(".btn-spinner").hide();
      });
  }

  $("#armForm").on("submit", function (e) {
    e.preventDefault();
    const id = $("#armId").val();
    const levelId = Number($("#armLevel").val());
    const name = $("#armName").val().trim();
    if (!name) return;

    const $btn = $("#armSaveBtn");
    $btn.prop("disabled", true).find(".btn-spinner").show();
    saveArm(id, { levelId: levelId, name: name }, $btn);
  });

  /* ---------------- Clear assignments ---------------- */

  $(document).on("click", ".js-clear-arm", function () {
    const id = Number($(this).closest("tr").data("id"));
    const arm = arms.find(function (a) { return a.id === id; });
    if (!arm) return;

    window.apiRequest("POST", "/api/classes/" + id + "/clear-assignments", {})
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Nothing to clear.", "success");
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status !== 409 || data.code !== "confirm_clear") return;
        const who = describeReplaces(data.replaces);
        const level = levelById(arm.levelId);
        const isPrimary = level && level.section === "primary";
        window.confirmAction({
          title: "Clear assignments for " + armLabel(arm) + "?",
          body: (who ? "This removes: " + who + ". " : "") +
            (isPrimary && data.hasClassTeacher ? "The class teacher is cleared too. " : "") +
            "Scores already entered are kept.",
          confirmLabel: "Clear assignments",
          danger: true,
          onConfirm: function () {
            window.apiRequest("POST", "/api/classes/" + id + "/clear-assignments", { confirm: true })
              .done(function (response) {
                if (response && response.success) {
                  loadClasses();
                  window.showToast("Assignments cleared.", "success");
                }
              });
          }
        });
      });
  });

  /* ---------------- Class teacher ---------------- */

  function classTeacherOtherArms(teacherId, currentArmId) {
    return arms.filter(function (a) {
      return a.classTeacherId === teacherId && a.id !== currentArmId;
    }).map(armLabel);
  }

  function updateClassTeacherNote() {
    const armId = Number($("#classTeacherArmId").val());
    const teacherId = Number($("#classTeacherSelect").val());
    const $note = $("#classTeacherNote");
    if (!teacherId) {
      $note.prop("hidden", true).text("");
      return;
    }
    const others = classTeacherOtherArms(teacherId, armId);
    if (others.length === 0) {
      $note.prop("hidden", true).text("");
    } else {
      $note.prop("hidden", false).text("This teacher is already class teacher of " + others.join(", ") + ".");
    }
  }

  $(document).on("click", ".js-class-teacher", function () {
    const id = Number($(this).closest("tr").data("id"));
    const arm = arms.find(function (a) { return a.id === id; });
    if (!arm) return;

    const $select = $("#classTeacherSelect").empty();
    $select.append($("<option>").val("").text("None"));
    teachers.forEach(function (t) {
      $select.append($("<option>").val(t.id).text(t.fullName));
    });
    // Keep the current class teacher selectable even if they have been deactivated.
    if (arm.classTeacherId && !teachers.some(function (t) { return t.id === arm.classTeacherId; })) {
      $select.append($("<option>").val(arm.classTeacherId).text((arm.classTeacherName || "Teacher") + " (inactive)"));
    }
    $select.val(arm.classTeacherId == null ? "" : String(arm.classTeacherId));

    $("#classTeacherArmId").val(arm.id);
    $("#classTeacherModalTitle").text("Class teacher: " + armLabel(arm));
    const level = levelById(arm.levelId);
    $("#classTeacherHelp").text(
      level && level.section === "primary"
        ? "This teacher will also teach every subject in this class."
        : "This teacher writes the class remark on report cards."
    );
    updateClassTeacherNote();
    window.openModal($("#classTeacherModal"));
  });

  $("#classTeacherSelect").on("change", updateClassTeacherNote);

  $("#classTeacherForm").on("submit", function (e) {
    e.preventDefault();
    const armId = Number($("#classTeacherArmId").val());
    const value = $("#classTeacherSelect").val();
    const teacherId = value === "" ? null : Number(value);

    const $btn = $("#classTeacherSaveBtn");
    $btn.prop("disabled", true).find(".btn-spinner").show();

    saveClassTeacher(armId, { teacherId: teacherId }, $btn);
  });

  function saveClassTeacher(armId, body, $btn) {
    window.apiRequest("PUT", "/api/classes/arms/" + armId + "/class-teacher", body)
      .done(function (response) {
        if (response && response.success) {
          loadClasses();
          window.closeModal($("#classTeacherModal"));
          window.showToast("Class teacher saved.", "success");
        }
      })
      .fail(function (xhr) {
        const data = xhr.responseJSON || {};
        if (xhr.status === 409 && data.code === "confirm_replace") {
          window.confirmAction({
            title: "Replace existing assignments?",
            body: "Setting this class teacher gives them every subject in this class and removes: " +
              describeReplaces(data.replaces) + ". Scores already entered are kept.",
            confirmLabel: "Replace",
            danger: true,
            onConfirm: function () {
              saveClassTeacher(armId, Object.assign({}, body, { confirmReplace: true }), $btn);
            }
          });
        }
      })
      .always(function () {
        $btn.prop("disabled", false).find(".btn-spinner").hide();
      });
  }

  loadClasses();
  loadTeachers();
});

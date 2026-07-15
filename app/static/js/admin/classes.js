/* ==========================================================================
   classes.js — Levels/Arms CRUD, wired to the real API.
   ========================================================================== */

$(function () {
  let levels = [];
  let arms = [];

  const $groups = $("#classesGroups");
  const $empty = $("#classesEmptyState");

  function render() {
    $groups.empty();
    if (levels.length === 0) {
      $empty.prop("hidden", false);
      return;
    }
    $empty.prop("hidden", true);

    levels.forEach(function (level) {
      const levelArms = arms.filter(function (a) { return a.levelId === level.id; });
      const $card = $('<div class="card mb-4"><div class="card-header"><h2></h2></div>' +
        '<div class="table-wrapper"><table class="data-table"><thead><tr>' +
        '<th>Arm</th><th>Students</th><th></th></tr></thead><tbody></tbody></table></div></div>');

      $card.find(".card-header h2").text(level.name);
      const $tbody = $card.find("tbody");

      if (levelArms.length === 0) {
        $tbody.append('<tr><td colspan="3" class="cell-muted">No arms yet for this level.</td></tr>');
      } else {
        levelArms.forEach(function (arm) {
          const $row = $(
            '<tr data-id="' + arm.id + '">' +
              "<td>" + level.name + " " + $("<div>").text(arm.name).html() + "</td>" +
              '<td class="cell-numeric">' + arm.studentCount + "</td>" +
              '<td class="row-actions">' +
                '<button type="button" class="btn btn-secondary btn-sm js-edit-arm"><i class="bi bi-pencil"></i></button>' +
                '<button type="button" class="btn btn-outline-danger btn-sm js-delete-arm"><i class="bi bi-trash"></i></button>' +
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
      $select.append('<option value="' + l.id + '">' + l.name + "</option>");
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

  $("#addLevelBtn").on("click", function () {
    $("#levelName").val("");
    window.openModal($("#levelModal"));
  });

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
      body: "This will permanently remove this arm. Students in it will need reassigning first.",
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

  $("#levelForm").on("submit", function (e) {
    e.preventDefault();
    const name = $("#levelName").val().trim();
    if (!name) return;

    const $btn = $("#levelSaveBtn");
    $btn.prop("disabled", true).find(".btn-spinner").show();

    window.apiRequest("POST", "/api/classes/levels", { name: name })
      .done(function (response) {
        if (response && response.success) {
          loadClasses();
          window.closeModal($("#levelModal"));
          window.showToast("Level added.", "success");
        }
      })
      .always(function () {
        $btn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  $("#armForm").on("submit", function (e) {
    e.preventDefault();
    const id = $("#armId").val();
    const levelId = Number($("#armLevel").val());
    const name = $("#armName").val().trim();
    if (!name) return;

    const $btn = $("#armSaveBtn");
    $btn.prop("disabled", true).find(".btn-spinner").show();

    const request = id
      ? window.apiRequest("PUT", "/api/classes/arms/" + id, { levelId: levelId, name: name })
      : window.apiRequest("POST", "/api/classes/arms", { levelId: levelId, name: name });

    request
      .done(function (response) {
        if (response && response.success) {
          loadClasses();
          window.showToast(id ? "Arm updated." : "Arm added.", "success");
          window.closeModal($("#armModal"));
        }
      })
      .always(function () {
        $btn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  loadClasses();
});

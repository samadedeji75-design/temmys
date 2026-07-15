/* ==========================================================================
   class-subjects.js — Class Arm -> Subject checklist, wired to the real API.
   ========================================================================== */

$(function () {
  let classArms = [];
  let subjects = [];

  const $picker = $("#classArmPicker");
  const $checklistCard = $("#subjectChecklistCard");
  const $noArmState = $("#noArmSelectedState");
  const $checklist = $("#subjectChecklist");
  const $armLabel = $("#selectedArmLabel");
  const $countBadge = $("#selectedCountBadge");
  const $saveBtn = $("#saveClassSubjectsBtn");

  function populatePicker() {
    $picker.empty().append('<option value="">Choose a class arm&hellip;</option>');
    classArms.forEach(function (arm) {
      $picker.append('<option value="' + arm.id + '">' + arm.label + "</option>");
    });
  }

  function updateCount() {
    const count = $checklist.find("input[type=checkbox]:checked").length;
    $countBadge.text(count + " selected");
  }

  function renderChecklist(assignedIds) {
    $checklist.empty();

    subjects.forEach(function (subject) {
      const checked = assignedIds.indexOf(subject.id) !== -1 ? "checked" : "";
      const $item = $(
        '<div class="form-group d-flex align-center gap-2" style="margin-bottom: var(--space-2);">' +
          '<input type="checkbox" id="subj_' + subject.id + '" value="' + subject.id + '" ' + checked + '>' +
          '<label class="form-label mb-0" for="subj_' + subject.id + '" style="cursor:pointer;">' +
            subject.name + ' <span class="text-muted text-sm">(' + (subject.code || '') + ')</span>' +
          "</label>" +
        "</div>"
      );
      $checklist.append($item);
    });
    updateCount();
  }

  function loadArmsAndSubjects() {
    // classes.js and this file both need /api/classes + /api/subjects — kept
    // as separate calls here since this page can be opened standalone.
    $.when(
      window.apiRequest("GET", "/api/classes"),
      window.apiRequest("GET", "/api/subjects")
    ).done(function (classesResp, subjectsResp) {
      const classesData = classesResp[0];
      const subjectsData = subjectsResp[0];
      if (!classesData.success || !subjectsData.success) return;

      classArms = classesData.arms.map(function (arm) {
        const level = classesData.levels.find(function (l) { return l.id === arm.levelId; });
        return { id: arm.id, label: (level ? level.name : "") + " " + arm.name };
      });
      subjects = subjectsData.subjects;
      populatePicker();
    });
  }

  $picker.on("change", function () {
    const armId = $(this).val();
    if (!armId) {
      $checklistCard.prop("hidden", true);
      $noArmState.show();
      return;
    }
    const arm = classArms.find(function (a) { return String(a.id) === armId; });
    $armLabel.text(arm.label);

    window.apiRequest("GET", "/api/classes/" + armId + "/subjects").done(function (response) {
      if (!response || !response.success) return;
      renderChecklist(response.subjectIds);
      $checklistCard.prop("hidden", false);
      $noArmState.hide();
    });
  });

  $(document).on("change", "#subjectChecklist input[type=checkbox]", updateCount);

  $saveBtn.on("click", function () {
    const armId = Number($picker.val());
    if (!armId) return;

    const selected = $checklist.find("input[type=checkbox]:checked")
      .map(function () { return Number($(this).val()); }).get();

    $saveBtn.prop("disabled", true).find(".btn-spinner").show();

    window.apiRequest("PUT", "/api/classes/" + armId + "/subjects", { subjectIds: selected })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Subjects saved for this class arm.", "success");
        }
      })
      .always(function () {
        $saveBtn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  $noArmState.show();
  $checklistCard.prop("hidden", true);
  loadArmsAndSubjects();
});

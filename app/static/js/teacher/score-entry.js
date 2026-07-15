/* ==========================================================================
   score-entry.js — teacher/score_entry.html, wired to the real API.

   Client-side CA Total / Subject Total / Grade calculations below are
   cosmetic only, for instant feedback as the teacher types. The server
   recalculates authoritatively on save (GradingScale-based grade, real
   ca_total/subject_total) and that recalculated response is what gets
   re-rendered — the client never trusts its own math for what's stored.
   ========================================================================== */

$(function () {
  const scoreTableBody = document.getElementById("scoreTableBody");
  if (!scoreTableBody) return;

  const classArmId = window.SCORE_ENTRY_CLASS_ARM_ID;
  const subjectId = window.SCORE_ENTRY_SUBJECT_ID;

  const $lockedBanner = $("#lockedBanner");
  const $saveAllBtn = $("#saveAllBtn");
  const $saveStatusSummary = $("#saveStatusSummary");

  let students = []; // current known-good state, as last returned by the server
  let caMax = 100;
  let examMax = 100;
  let termLocked = false;

  function gradeLabel(row) {
    return row.grade || "—";
  }

  function computeLocalCaTotal(row) {
    const parts = [row.ca1, row.ca2, row.ca3];
    if (parts.some(function (p) { return p === null || p === "" || Number.isNaN(Number(p)); })) return null;
    return parts.reduce(function (sum, p) { return sum + Number(p); }, 0);
  }

  function computeLocalSubjectTotal(row) {
    const ca = computeLocalCaTotal(row);
    if (ca === null || row.examScore === null || row.examScore === "") return null;
    return ca + Number(row.examScore);
  }

  function fieldCell(row, field) {
    const value = row[field] === null || row[field] === undefined ? "" : row[field];
    return (
      '<span class="score-cell-tooltip">' +
        '<input type="number" class="score-input js-score-input" data-field="' + field + '" ' +
          'value="' + value + '" min="0" ' + (termLocked ? "disabled" : "") + '>' +
        '<span class="tooltip-bubble"></span>' +
      "</span>"
    );
  }

  function render() {
    scoreTableBody.innerHTML = "";

    students.forEach(function (row) {
      const ca = computeLocalCaTotal(row);
      const total = computeLocalSubjectTotal(row);
      const tr = document.createElement("tr");
      tr.dataset.studentId = row.studentId;

      tr.innerHTML =
        "<td>" + $("<div>").text(row.fullName).html() + "</td>" +
        "<td>" + fieldCell(row, "ca1") + "</td>" +
        "<td>" + fieldCell(row, "ca2") + "</td>" +
        "<td>" + fieldCell(row, "ca3") + "</td>" +
        "<td>" + fieldCell(row, "examScore") + "</td>" +
        '<td class="cell-numeric js-ca-total" style="font-weight:600;">' + (ca === null ? "—" : ca) + "</td>" +
        '<td class="cell-numeric js-subject-total" style="font-weight:700; color: var(--color-primary);">' + (total === null ? "—" : total) + "</td>" +
        '<td class="js-grade"><span class="badge badge-info">' + gradeLabel(row) + "</span></td>" +
        '<td><span class="row-save-dot saved" title="Saved"><i class="bi bi-check"></i></span></td>';

      scoreTableBody.appendChild(tr);
    });

    updateSaveSummary();
  }

  function updateSaveSummary() {
    const unsavedCount = scoreTableBody.querySelectorAll(".row-save-dot.unsaved").length;
    $saveStatusSummary.text(
      unsavedCount === 0 ? "All scores saved." : unsavedCount + " row" + (unsavedCount > 1 ? "s" : "") + " with unsaved changes."
    );
    $saveStatusSummary.css("color", unsavedCount === 0 ? "var(--color-text-muted)" : "var(--color-warning)");
  }

  function applyLockedState() {
    $lockedBanner.toggle(termLocked);
    $saveAllBtn.prop("disabled", termLocked).toggle(!termLocked);
    scoreTableBody.querySelectorAll(".score-input").forEach(function (input) {
      input.disabled = termLocked;
    });
  }

  function loadScores() {
    window.apiRequest("GET", "/api/teacher/scores?classArmId=" + classArmId + "&subjectId=" + subjectId)
      .done(function (response) {
        if (!response || !response.success) return;
        students = response.students;
        caMax = response.caMax;
        examMax = response.examMax;
        termLocked = response.termLocked;
        render();
        applyLockedState();
      });
  }

  scoreTableBody.addEventListener("input", function (e) {
    const input = e.target.closest(".js-score-input");
    if (!input) return;

    const tr = input.closest("tr");
    const studentId = Number(tr.dataset.studentId);
    const field = input.dataset.field;
    const row = students.find(function (r) { return r.studentId === studentId; });
    if (!row) return;

    const rawValue = input.value === "" ? null : Number(input.value);
    row[field] = rawValue;

    // Cosmetic over-max flag — the field-level max isn't known individually
    // per CA component server-side (only the aggregate ca_max_score /
    // exam_max_score), so we flag against the aggregate where relevant.
    const wrapper = input.closest(".score-cell-tooltip");
    const ca = computeLocalCaTotal(row);
    const overCaMax = field !== "examScore" && ca !== null && ca > caMax;
    const overExamMax = field === "examScore" && rawValue !== null && rawValue > examMax;

    if (overCaMax || overExamMax) {
      input.classList.add("is-invalid");
      wrapper.querySelector(".tooltip-bubble").textContent = overExamMax
        ? "Exam max is " + examMax
        : "CA total max is " + caMax;
      wrapper.classList.add("show-tooltip");
    } else {
      input.classList.remove("is-invalid");
      wrapper.classList.remove("show-tooltip");
    }

    const total = computeLocalSubjectTotal(row);
    tr.querySelector(".js-ca-total").textContent = ca === null ? "—" : ca;
    tr.querySelector(".js-subject-total").textContent = total === null ? "—" : total;

    const dot = tr.querySelector(".row-save-dot");
    dot.className = "row-save-dot unsaved";
    dot.title = "Unsaved changes";
    dot.innerHTML = '<i class="bi bi-circle-fill"></i>';

    updateSaveSummary();
  });

  scoreTableBody.addEventListener("blur", function (e) {
    const wrapper = e.target.closest(".score-cell-tooltip");
    if (wrapper && !wrapper.querySelector(".js-score-input").classList.contains("is-invalid")) {
      wrapper.classList.remove("show-tooltip");
    }
  }, true);

  $saveAllBtn.on("click", function () {
    if (termLocked) return;

    const hasInvalid = scoreTableBody.querySelector(".is-invalid");
    if (hasInvalid) {
      window.showToast("Fix scores exceeding the max before saving.", "danger");
      return;
    }

    const payloadScores = students.map(function (row) {
      return {
        studentId: row.studentId,
        ca1: row.ca1 === null ? 0 : row.ca1,
        ca2: row.ca2 === null ? 0 : row.ca2,
        ca3: row.ca3 === null ? 0 : row.ca3,
        examScore: row.examScore === null ? 0 : row.examScore,
      };
    });

    $saveAllBtn.prop("disabled", true).find(".btn-spinner").show();

    window.apiRequest("POST", "/api/teacher/scores", {
      classArmId: classArmId,
      subjectId: subjectId,
      scores: payloadScores,
    })
      .done(function (response) {
        if (!response || !response.success) return;
        students = response.students;
        caMax = response.caMax;
        examMax = response.examMax;
        termLocked = response.termLocked;
        render();
        applyLockedState();
        window.showToast("All scores saved.", "success");
      })
      .fail(function (xhr) {
        const body = xhr.responseJSON;
        if (body && body.errors && body.errors.length) {
          window.showToast(body.errors[0] + (body.errors.length > 1 ? " (+" + (body.errors.length - 1) + " more)" : ""), "danger");
        }
      })
      .always(function () {
        $saveAllBtn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  loadScores();
});
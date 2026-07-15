/* grading-scale.js — wired to the real API (GET/POST /api/grading-scale). */

(function () {
  "use strict";

  const tableBody = document.getElementById("gradingTableBody");
  if (!tableBody) return;

  const caMaxInput = document.getElementById("caMax");
  const examMaxInput = document.getElementById("examMax");
  const totalCheckLabel = document.getElementById("totalCheckLabel");
  const addRowBtn = document.getElementById("addGradeRowBtn");
  const saveBtn = document.getElementById("saveGradingScaleBtn");
  const validationAlert = document.getElementById("gradingValidationAlert");
  const validationText = document.getElementById("gradingValidationText");

  let rows = [];
  let nextId = -1; // negative temp ids for new, unsaved rows

  function checkCaExamTotal() {
    const total = (Number(caMaxInput.value) || 0) + (Number(examMaxInput.value) || 0);
    totalCheckLabel.innerHTML = `Total: <strong style="color:${total === 100 ? "var(--color-success)" : "var(--color-danger)"}">${total}</strong>${total === 100 ? "" : " — should equal 100"}`;
  }

  caMaxInput.addEventListener("input", checkCaExamTotal);
  examMaxInput.addEventListener("input", checkCaExamTotal);

  function renderRows() {
    tableBody.innerHTML = "";

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.dataset.rowId = row.id;
      tr.innerHTML = `
        <td><input type="number" class="table-inline-input js-min" value="${row.min}" min="0" max="100"></td>
        <td><input type="number" class="table-inline-input js-max" value="${row.max}" min="0" max="100"></td>
        <td><input type="text" class="table-inline-input js-grade" value="${row.grade}" maxlength="2" style="text-align:center; font-weight:700;"></td>
        <td><input type="text" class="table-inline-input js-remark" value="${row.remark || ""}"></td>
        <td>
          <button type="button" class="btn-link js-delete-row" style="color: var(--color-danger);" aria-label="Delete row">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      `;
      tableBody.appendChild(tr);
    });

    validateRows();
  }

  function readRowsFromDom() {
    return Array.from(tableBody.querySelectorAll("tr")).map((tr) => ({
      id: Number(tr.dataset.rowId),
      min: Number(tr.querySelector(".js-min").value),
      max: Number(tr.querySelector(".js-max").value),
      grade: tr.querySelector(".js-grade").value.trim(),
      remark: tr.querySelector(".js-remark").value.trim(),
    }));
  }

  function validateRows() {
    const current = readRowsFromDom();
    const issues = [];

    tableBody.querySelectorAll(".table-inline-input").forEach((el) => el.classList.remove("is-invalid"));

    current.forEach((row, i) => {
      const tr = tableBody.children[i];
      if (row.min > row.max) {
        tr.querySelector(".js-min").classList.add("is-invalid");
        tr.querySelector(".js-max").classList.add("is-invalid");
        issues.push(`Row for grade "${row.grade || "?"}": min score is greater than max score.`);
      }
      if (!row.grade) {
        tr.querySelector(".js-grade").classList.add("is-invalid");
        issues.push(`Row ${i + 1}: grade letter is required.`);
      }
    });

    const sorted = [...current].sort((a, b) => a.min - b.min);
    for (let i = 0; i < sorted.length - 1; i++) {
      const a = sorted[i];
      const b = sorted[i + 1];
      if (a.max >= b.min) {
        issues.push(`Overlap: "${a.grade || "?"}" (${a.min}–${a.max}) overlaps with "${b.grade || "?"}" (${b.min}–${b.max}).`);
        markRowInvalid(a.id);
        markRowInvalid(b.id);
      } else if (b.min - a.max > 1) {
        issues.push(`Gap: no grade covers scores ${a.max + 1}–${b.min - 1}, between "${a.grade || "?"}" and "${b.grade || "?"}".`);
      }
    }

    if (issues.length > 0) {
      validationAlert.style.display = "";
      validationText.innerHTML = issues.map((i) => `<div>${i}</div>`).join("");
    } else {
      validationAlert.style.display = "none";
    }

    return issues.length === 0;
  }

  function markRowInvalid(id) {
    const tr = tableBody.querySelector(`tr[data-row-id="${id}"]`);
    if (tr) {
      tr.querySelector(".js-min").classList.add("is-invalid");
      tr.querySelector(".js-max").classList.add("is-invalid");
    }
  }

  function loadGradingScale() {
    window.apiRequest("GET", "/api/grading-scale").done(function (response) {
      if (!response || !response.success) return;
      caMaxInput.value = response.caMax;
      examMaxInput.value = response.examMax;
      rows = response.rows.map((r) => ({ id: r.id, min: r.min, max: r.max, grade: r.grade, remark: r.remark || "" }));
      checkCaExamTotal();
      renderRows();
    });
  }

  tableBody.addEventListener("input", () => validateRows());

  tableBody.addEventListener("click", (e) => {
    const deleteBtn = e.target.closest(".js-delete-row");
    if (!deleteBtn) return;
    const tr = deleteBtn.closest("tr");
    const id = Number(tr.dataset.rowId);
    rows = readRowsFromDom().filter((r) => r.id !== id);
    renderRows();
  });

  addRowBtn.addEventListener("click", () => {
    rows = readRowsFromDom();
    rows.push({ id: nextId--, min: 0, max: 0, grade: "", remark: "" });
    renderRows();
    const lastInput = tableBody.querySelector("tr:last-child .js-min");
    if (lastInput) lastInput.focus();
  });

  saveBtn.addEventListener("click", () => {
    rows = readRowsFromDom();
    const valid = validateRows();
    if (!valid) {
      window.showToast("Fix the flagged grade bands before saving.", "danger");
      return;
    }

    saveBtn.disabled = true;
    const originalLabel = saveBtn.querySelector(".btn-label").textContent;
    saveBtn.innerHTML = `<span class="btn-spinner"></span> Saving…`;

    window.apiRequest("POST", "/api/grading-scale", {
      caMax: Number(caMaxInput.value),
      examMax: Number(examMaxInput.value),
      rows: rows,
    })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Grading scale saved.", "success");
          loadGradingScale(); // re-fetch so temp negative ids become real DB ids
        }
      })
      .always(function () {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<span class="btn-label">${originalLabel}</span>`;
      });
  });

  loadGradingScale();
})();

/* ==========================================================================
   class-remarks.js — teacher/class_remarks.html, wired to the real API.
   ========================================================================== */

$(function () {
  const tableBody = document.getElementById("remarksTableBody");
  if (!tableBody) return;

  const emptyState = document.getElementById("remarksEmptyState");
  const armId = window.CLASS_REMARKS_ARM_ID;

  function escapeHtml(str) {
    return $("<div>").text(str || "").html();
  }

  function renderRows(results) {
    tableBody.innerHTML = "";

    if (!results.length) {
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;

    results.forEach(function (r) {
      const tr = document.createElement("tr");
      tr.dataset.resultId = r.resultId;
      tr.innerHTML =
        '<td style="font-weight:600;">' + escapeHtml(r.fullName) + "</td>" +
        '<td class="cell-muted">' + escapeHtml(r.admissionNumber) + "</td>" +
        '<td><textarea class="form-control js-remark-input" rows="2" maxlength="1000">' + escapeHtml(r.classTeacherRemark) + "</textarea></td>" +
        '<td><button type="button" class="btn btn-secondary btn-sm js-save-remark-btn">Save</button></td>';
      tableBody.appendChild(tr);
    });
  }

  function loadRemarks() {
    window.apiRequest("GET", `/api/teacher/classes/${armId}/remarks`).done(function (response) {
      if (!response || !response.success) return;
      renderRows(response.results || []);
    });
  }

  tableBody.addEventListener("click", function (e) {
    const btn = e.target.closest(".js-save-remark-btn");
    if (!btn) return;

    const tr = btn.closest("tr");
    const resultId = tr.dataset.resultId;
    const textarea = tr.querySelector(".js-remark-input");
    const originalLabel = btn.textContent;

    btn.disabled = true;
    btn.textContent = "Saving…";

    window.apiRequest("POST", `/api/teacher/results/${resultId}/remarks`, {
      classTeacherRemark: textarea.value,
    })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Remark saved.", "success");
        }
      })
      .always(function () {
        btn.disabled = false;
        btn.textContent = originalLabel;
      });
  });

  loadRemarks();
});

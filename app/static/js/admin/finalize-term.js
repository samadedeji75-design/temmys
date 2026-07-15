/* finalize-term.js — real backend-driven logic for finalize_term.html and
   class_result_overview.html. */

$(function () {
  "use strict";

  /* -----------------------------------------------------------------------
     finalize_term.html
     ----------------------------------------------------------------------- */
  const finalizeTableBody = document.getElementById("finalizeTableBody");

  if (finalizeTableBody) {
    let classes = [];

    const overrideModal = document.getElementById("overrideModal");
    const overrideModalTitle = document.getElementById("overrideModalTitle");
    const incompleteList = document.getElementById("incompleteList");
    const confirmOverrideBtn = document.getElementById("confirmOverrideBtn");
    let pendingClassArmId = null;

    function completionPercent(cls) {
      return cls.totalStudents === 0 ? 0 : Math.round((cls.completeStudents / cls.totalStudents) * 100);
    }

    function progressClass(pct) {
      if (pct >= 100) return "complete";
      if (pct === 0) return "empty";
      return "partial";
    }

    function renderClasses() {
      finalizeTableBody.innerHTML = "";

      classes.forEach((cls) => {
        const pct = completionPercent(cls);
        const tr = document.createElement("tr");

        let statusBadge;
        if (cls.isFinalized) statusBadge = `<span class="badge badge-success"><i class="bi bi-lock-fill"></i> Finalized</span>`;
        else if (!cls.canFinalize) statusBadge = `<span class="badge badge-neutral">Not Ready</span>`;
        else if (pct >= 100) statusBadge = `<span class="badge badge-info">Ready</span>`;
        else if (pct === 0) statusBadge = `<span class="badge badge-neutral">Not Started</span>`;
        else statusBadge = `<span class="badge badge-warning">In Progress</span>`;

        let actionCell;
        if (cls.isFinalized) {
          actionCell = `<a href="/admin/results/${cls.classArmId}/overview" class="btn btn-secondary btn-sm">View Results</a>`;
        } else if (!cls.canFinalize) {
          actionCell = `<button type="button" class="btn btn-outline-danger btn-sm" disabled title="No students or no subjects assigned">Finalize</button>`;
        } else {
          actionCell = `<button type="button" class="btn ${pct >= 100 ? "btn-primary" : "btn-outline-danger"} btn-sm js-finalize-btn" data-class-arm-id="${cls.classArmId}">
                          ${pct >= 100 ? "Finalize" : "Finalize…"}
                        </button>`;
        }

        tr.innerHTML = `
          <td style="font-weight:600;">${cls.label}</td>
          <td class="cell-muted">${cls.completeStudents} / ${cls.totalStudents} scores entered</td>
          <td>
            <div class="progress-row">
              <div class="progress-track"><div class="progress-fill ${progressClass(pct)}" style="width:${pct}%;"></div></div>
              <span class="progress-label">${pct}%</span>
            </div>
          </td>
          <td>${statusBadge}</td>
          <td>${actionCell}</td>
        `;
        finalizeTableBody.appendChild(tr);
      });
    }

    function loadStatus() {
      window.apiRequest("GET", "/api/finalize/status").done(function (response) {
        classes = response.classes || [];
        renderClasses();
      });
    }

    finalizeTableBody.addEventListener("click", (e) => {
      const btn = e.target.closest(".js-finalize-btn");
      if (!btn) return;
      const classArmId = parseInt(btn.dataset.classArmId, 10);
      const cls = classes.find((c) => c.classArmId === classArmId);
      if (!cls) return;
      const pct = completionPercent(cls);

      if (pct >= 100) {
        finalizeClass(classArmId);
      } else {
        pendingClassArmId = classArmId;
        overrideModalTitle.textContent = `Finalize ${cls.label} with incomplete scores?`;
        incompleteList.innerHTML = cls.incompleteStudentNames && cls.incompleteStudentNames.length
          ? cls.incompleteStudentNames.map((name) => `<div class="incomplete-list-item"><span>${name}</span><span class="text-muted">Missing scores</span></div>`).join("")
          : `<div class="incomplete-list-item"><span class="text-muted">Individual student breakdown unavailable.</span></div>`;
        overrideModal.classList.add("show");
      }
    });

    function closeOverrideModal() {
      overrideModal.classList.remove("show");
      pendingClassArmId = null;
    }
    document.getElementById("overrideModalClose").addEventListener("click", closeOverrideModal);
    overrideModal.querySelectorAll("[data-modal-dismiss]").forEach((el) => el.addEventListener("click", closeOverrideModal));
    overrideModal.addEventListener("click", (e) => { if (e.target === overrideModal) closeOverrideModal(); });

    confirmOverrideBtn.addEventListener("click", () => {
      if (pendingClassArmId) finalizeClass(pendingClassArmId);
      closeOverrideModal();
    });

    function finalizeClass(classArmId) {
      const cls = classes.find((c) => c.classArmId === classArmId);
      if (!cls) return;
      window.apiRequest("POST", `/api/finalize/${classArmId}`).done(function () {
        window.showToast(`${cls.label} finalized. Results are now visible to parents.`, "success");
        loadStatus();
      });
    }

    const refreshBtn = document.getElementById("refreshFinalizeBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", loadStatus);
    }

    loadStatus();
  }

  /* -----------------------------------------------------------------------
     class_result_overview.html
     ----------------------------------------------------------------------- */
  const overviewTableBody = document.getElementById("overviewTableBody");

  if (overviewTableBody) {
    const armId = window.CLASS_RESULT_OVERVIEW_ARM_ID;

    function medalClass(position) {
      if (position === 1) return "gold";
      if (position === 2) return "silver";
      if (position === 3) return "bronze";
      return "";
    }

    function renderOverview(results, isFinalized) {
      overviewTableBody.innerHTML = "";

      const emptyState = document.getElementById("overviewEmptyState");

      if (!isFinalized || !results.length) {
        if (emptyState) emptyState.hidden = false;
        return;
      }
      if (emptyState) emptyState.hidden = true;

      results.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="position-badge ${medalClass(r.position)}">${r.position}</span></td>
          <td style="font-weight:600;">${r.fullName}</td>
          <td class="cell-muted">${r.admissionNumber}</td>
          <td class="cell-numeric">${r.cumulativeTotal}</td>
          <td class="cell-numeric">${r.cumulativeAverage.toFixed ? r.cumulativeAverage.toFixed(1) : r.cumulativeAverage}%</td>
          <td><span class="badge badge-info">${r.overallGrade || "—"}</span></td>
          <td>
            <a href="/admin/results/${r.resultId}" class="btn btn-secondary btn-sm">View</a>
          </td>
        `;
        overviewTableBody.appendChild(tr);
      });
    }

    function loadOverview() {
      window.apiRequest("GET", `/api/results/${armId}/overview`).done(function (response) {
        renderOverview(response.results || [], response.isFinalized);
      });
    }

    document.getElementById("downloadBatchBtn").addEventListener("click", () => {
      window.location.href = `/admin/results/${armId}/batch-pdf`;
    });

    loadOverview();
  }
});

/* portal.js — real backend-driven logic for portal/dashboard.html and
   portal/result_view.html. */

$(function () {
  "use strict";

  /* -----------------------------------------------------------------------
     portal/dashboard.html
     ----------------------------------------------------------------------- */
  const termCardGrid = document.getElementById("termCardGrid");

  if (termCardGrid) {
    window.apiRequest("GET", "/api/portal/student").done(function (response) {
      if (!response || !response.success) return;
      const student = response.student;

      document.getElementById("studentAvatarInitial").textContent = student.fullName
        .split(" ")
        .map((p) => p.charAt(0))
        .join("")
        .slice(0, 2)
        .toUpperCase();
      document.getElementById("studentNameLabel").textContent = student.fullName;
      document.getElementById("studentMetaLabel").textContent = `${student.classLabel} · ${student.admissionNumber}`;
    });

    window.apiRequest("GET", "/api/portal/finalized-terms").done(function (response) {
      if (!response || !response.success) return;
      const terms = response.terms || [];

      const emptyState = document.getElementById("portalEmptyState");

      if (terms.length === 0) {
        emptyState.style.display = "";
        return;
      }

      terms.forEach((t) => {
        const card = document.createElement("a");
        card.href = `/portal/results/${t.resultId}`;
        card.className = "term-card";
        card.innerHTML = `
          <div class="term-card-title">${t.termLabel}</div>
          <div class="term-card-meta">${t.sessionLabel} Session</div>
          <div class="term-card-meta">Average: <strong>${t.average}%</strong> &middot; Grade: <strong>${t.grade || "—"}</strong></div>
          <div class="term-card-cta">View Result <i class="bi bi-arrow-right"></i></div>
        `;
        termCardGrid.appendChild(card);
      });
    });
  }

  /* -----------------------------------------------------------------------
     portal/result_view.html
     ----------------------------------------------------------------------- */
  const downloadPdfBtn = document.getElementById("downloadPdfBtn");

  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener("click", function () {
      window.location.href = `/portal/results/${downloadPdfBtn.dataset.resultId}/pdf`;
    });
  }
});

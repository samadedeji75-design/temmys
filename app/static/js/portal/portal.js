/* portal.js — front-end-only logic for portal/dashboard.html and
   portal/result_view.html. All data is mock/in-memory. Every point that
   will eventually call the backend is marked with // TODO: wire to backend */

(function () {
  "use strict";

  /* -----------------------------------------------------------------------
     portal/dashboard.html
     ----------------------------------------------------------------------- */
  const termCardGrid = document.getElementById("termCardGrid");

  if (termCardGrid) {
    // TODO: wire to backend — GET /api/portal/student (logged-in student's identity)
    const student = { name: "Funmilayo Bello", classLabel: "JSS3 A", admissionNumber: "STU/2024/0088" };

    document.getElementById("studentAvatarInitial").textContent = student.name
      .split(" ")
      .map((p) => p.charAt(0))
      .join("")
      .slice(0, 2)
      .toUpperCase();
    document.getElementById("studentNameLabel").textContent = student.name;
    document.getElementById("studentMetaLabel").textContent = `${student.classLabel} · ${student.admissionNumber}`;

    // TODO: wire to backend — GET /api/portal/finalized-terms
    const finalizedTerms = [
      { label: "First Term", session: "2025/2026 Session", average: "85.0%", grade: "A", href: "/portal/result?term=first-2025-2026" },
      { label: "Third Term", session: "2024/2025 Session", average: "81.4%", grade: "A", href: "/portal/result?term=third-2024-2025" },
      { label: "Second Term", session: "2024/2025 Session", average: "78.9%", grade: "B", href: "/portal/result?term=second-2024-2025" },
    ];

    const emptyState = document.getElementById("portalEmptyState");

    if (finalizedTerms.length === 0) {
      emptyState.style.display = "";
    } else {
      finalizedTerms.forEach((t) => {
        const card = document.createElement("a");
        card.href = t.href;
        card.className = "term-card";
        card.innerHTML = `
          <div class="term-card-title">${t.label}</div>
          <div class="term-card-meta">${t.session}</div>
          <div class="term-card-meta">Average: <strong>${t.average}</strong> &middot; Grade: <strong>${t.grade}</strong></div>
          <div class="term-card-cta">View Result <i class="bi bi-arrow-right"></i></div>
        `;
        termCardGrid.appendChild(card);
      });
    }
  }

  /* -----------------------------------------------------------------------
     portal/result_view.html
     ----------------------------------------------------------------------- */
  const downloadPdfBtn = document.getElementById("downloadPdfBtn");

  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener("click", () => {
      downloadPdfBtn.disabled = true;
      const originalLabel = downloadPdfBtn.querySelector(".btn-label").innerHTML;
      downloadPdfBtn.innerHTML = `<span class="btn-spinner"></span> Preparing PDF…`;

      // TODO: wire to backend — GET /api/portal/result/pdf (renders result_print.html server-side to PDF)
      setTimeout(() => {
        downloadPdfBtn.disabled = false;
        downloadPdfBtn.innerHTML = `<span class="btn-label">${originalLabel}</span>`;
        window.showToast("PDF ready for download.", "success");
      }, 900);
    });
  }
})();
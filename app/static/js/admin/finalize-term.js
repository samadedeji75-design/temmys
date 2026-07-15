/* finalize-term.js — front-end-only logic for finalize_term.html and
   class_result_overview.html. All data is mock/in-memory. Every point that
   will eventually call the backend is marked with // TODO: wire to backend */

(function () {
  "use strict";

  /* -----------------------------------------------------------------------
     finalize_term.html
     ----------------------------------------------------------------------- */
  const finalizeTableBody = document.getElementById("finalizeTableBody");

  if (finalizeTableBody) {
    // TODO: wire to backend — GET /api/term/finalization-status (poll or websocket)
    let classes = [
      {
        classArm: "jss1a", label: "JSS1 A", total: 32, entered: 32, finalized: false,
        incompleteStudents: [],
      },
      {
        classArm: "jss1b", label: "JSS1 B", total: 30, entered: 22, finalized: false,
        incompleteStudents: ["Uche Nnamdi", "Peace Igwe", "Samuel Danjuma"],
      },
      {
        classArm: "jss2a", label: "JSS2 A", total: 28, entered: 28, finalized: true,
        incompleteStudents: [],
      },
      {
        classArm: "jss3a", label: "JSS3 A", total: 25, entered: 0, finalized: false,
        incompleteStudents: [],
      },
      {
        classArm: "ss1a", label: "SS1 A", total: 27, entered: 19, finalized: false,
        incompleteStudents: ["Halima Yusuf", "Godwin Effiong"],
      },
    ];

    const overrideModal = document.getElementById("overrideModal");
    const overrideModalTitle = document.getElementById("overrideModalTitle");
    const incompleteList = document.getElementById("incompleteList");
    const confirmOverrideBtn = document.getElementById("confirmOverrideBtn");
    let pendingOverrideClassArm = null;

    function completionPercent(cls) {
      return cls.total === 0 ? 0 : Math.round((cls.entered / cls.total) * 100);
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
        if (cls.finalized) statusBadge = `<span class="badge badge-success"><i class="bi bi-lock-fill"></i> Finalized</span>`;
        else if (pct >= 100) statusBadge = `<span class="badge badge-info">Ready</span>`;
        else if (pct === 0) statusBadge = `<span class="badge badge-neutral">Not Started</span>`;
        else statusBadge = `<span class="badge badge-warning">In Progress</span>`;

        tr.innerHTML = `
          <td style="font-weight:600;">${cls.label}</td>
          <td class="cell-muted">${cls.entered} / ${cls.total} scores entered</td>
          <td>
            <div class="progress-row">
              <div class="progress-track"><div class="progress-fill ${progressClass(pct)}" style="width:${pct}%;"></div></div>
              <span class="progress-label">${pct}%</span>
            </div>
          </td>
          <td>${statusBadge}</td>
          <td>
            ${cls.finalized
              ? `<a href="/admin/class-result-overview?class=${cls.classArm}" class="btn btn-secondary btn-sm">View Results</a>`
              : `<button type="button" class="btn ${pct >= 100 ? "btn-primary" : "btn-outline-danger"} btn-sm js-finalize-btn" data-class="${cls.classArm}">
                   ${pct >= 100 ? "Finalize" : "Finalize…"}
                 </button>`
            }
          </td>
        `;
        finalizeTableBody.appendChild(tr);
      });
    }

    finalizeTableBody.addEventListener("click", (e) => {
      const btn = e.target.closest(".js-finalize-btn");
      if (!btn) return;
      const classArm = btn.dataset.class;
      const cls = classes.find((c) => c.classArm === classArm);
      const pct = completionPercent(cls);

      if (pct >= 100) {
        finalizeClass(classArm);
      } else {
        pendingOverrideClassArm = classArm;
        overrideModalTitle.textContent = `Finalize ${cls.label} with incomplete scores?`;
        incompleteList.innerHTML = cls.incompleteStudents.length
          ? cls.incompleteStudents.map((name) => `<div class="incomplete-list-item"><span>${name}</span><span class="text-muted">Missing scores</span></div>`).join("")
          : `<div class="incomplete-list-item"><span class="text-muted">Individual student breakdown unavailable in preview.</span></div>`;
        overrideModal.classList.add("show");
      }
    });

    function closeOverrideModal() {
      overrideModal.classList.remove("show");
      pendingOverrideClassArm = null;
    }
    document.getElementById("overrideModalClose").addEventListener("click", closeOverrideModal);
    overrideModal.querySelectorAll("[data-modal-dismiss]").forEach((el) => el.addEventListener("click", closeOverrideModal));
    overrideModal.addEventListener("click", (e) => { if (e.target === overrideModal) closeOverrideModal(); });

    confirmOverrideBtn.addEventListener("click", () => {
      if (pendingOverrideClassArm) finalizeClass(pendingOverrideClassArm);
      closeOverrideModal();
    });

    function finalizeClass(classArm) {
      const cls = classes.find((c) => c.classArm === classArm);
      if (!cls) return;
      // TODO: wire to backend — POST /api/classes/:classArm/finalize
      cls.finalized = true;
      renderClasses();
      window.showToast(`${cls.label} finalized. Results are now visible to parents.`, "success");
    }

    // Polling stub — simulates teachers entering scores in real time.
    // TODO: wire to backend — replace with real polling/websocket of finalization status
    setInterval(() => {
      let changed = false;
      classes.forEach((cls) => {
        if (!cls.finalized && cls.entered < cls.total && Math.random() < 0.35) {
          cls.entered = Math.min(cls.total, cls.entered + 1);
          if (cls.incompleteStudents.length && cls.entered / cls.total > 0.5) {
            cls.incompleteStudents.pop();
          }
          changed = true;
        }
      });
      if (changed) renderClasses();
    }, 3000);

    renderClasses();
  }

  /* -----------------------------------------------------------------------
     class_result_overview.html
     ----------------------------------------------------------------------- */
  const overviewTableBody = document.getElementById("overviewTableBody");

  if (overviewTableBody) {
    // TODO: wire to backend — GET /api/classes/:classArm/result-overview
    const results = [
      { id: "1", name: "Funmilayo Bello", admissionNumber: "STU/2024/0088", total: 542, average: 90.3 },
      { id: "2", name: "David Okonkwo", admissionNumber: "STU/2022/0011", total: 531, average: 88.5 },
      { id: "3", name: "Ibrahim Suleiman", admissionNumber: "STU/2023/0034", total: 519, average: 86.5 },
      { id: "4", name: "Grace Udo", admissionNumber: "STU/2023/0035", total: 498, average: 83.0 },
      { id: "5", name: "Tobi Adewale", admissionNumber: "STU/2025/0102", total: 470, average: 78.3 },
      { id: "6", name: "Chiamaka Eze", admissionNumber: "STU/2025/0103", total: 455, average: 75.8 },
      { id: "7", name: "Adaeze Okafor", admissionNumber: "STU/2025/0101", total: 401, average: 66.8 },
      { id: "8", name: "Emeka Nwosu", admissionNumber: "STU/2024/0087", total: 358, average: 59.7 },
    ];

    function gradeFor(average) {
      if (average >= 70) return "A";
      if (average >= 60) return "B";
      if (average >= 50) return "C";
      if (average >= 45) return "D";
      if (average >= 40) return "E";
      return "F";
    }

    function medalClass(position) {
      if (position === 1) return "gold";
      if (position === 2) return "silver";
      if (position === 3) return "bronze";
      return "";
    }

    function renderOverview() {
      const sorted = [...results].sort((a, b) => b.average - a.average);
      overviewTableBody.innerHTML = "";

      sorted.forEach((r, i) => {
        const position = i + 1;
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="position-badge ${medalClass(position)}">${position}</span></td>
          <td style="font-weight:600;">${r.name}</td>
          <td class="cell-muted">${r.admissionNumber}</td>
          <td class="cell-numeric">${r.total}</td>
          <td class="cell-numeric">${r.average.toFixed(1)}%</td>
          <td><span class="badge badge-info">${gradeFor(r.average)}</span></td>
          <td>
            <a href="/admin/students/${r.id}/result" class="btn btn-secondary btn-sm">View</a>
          </td>
        `;
        overviewTableBody.appendChild(tr);
      });
    }

    document.getElementById("downloadBatchBtn").addEventListener("click", (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      const originalLabel = btn.querySelector(".btn-label").innerHTML;
      btn.innerHTML = `<span class="btn-spinner"></span> Preparing PDF…`;

      // TODO: wire to backend — GET /api/classes/:classArm/result-overview/pdf (streams a batch PDF)
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-label">${originalLabel}</span>`;
        window.showToast("Batch PDF ready for download.", "success");
      }, 900);
    });

    renderOverview();
  }
})();
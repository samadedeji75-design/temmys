/* admin/student-result.js — student_result.html
   PDF generation is Phase 7 (ReportLab). The button stays visible but must
   not pretend to work — disable it with an explanatory title rather than
   faking success. */

(function () {
  "use strict";

  const btn = document.getElementById("downloadPdfBtn");
  if (btn) {
    btn.disabled = true;
    btn.setAttribute("title", "PDF export arrives in Phase 7.");
  }
})();

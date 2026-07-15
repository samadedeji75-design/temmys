/* admin/student-result.js — student_result.html */

$(function () {
  "use strict";

  const downloadBtn = document.getElementById("downloadPdfBtn");
  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () {
      window.location.href = `/admin/results/${downloadBtn.dataset.resultId}/pdf`;
    });
  }

  const saveRemarksBtn = document.getElementById("saveRemarksBtn");
  if (saveRemarksBtn) {
    const classTeacherInput = document.getElementById("classTeacherRemarkInput");
    const principalInput = document.getElementById("principalRemarkInput");
    const classTeacherText = document.getElementById("resultClassTeacherRemarkText");
    const principalText = document.getElementById("resultPrincipalRemarkText");

    saveRemarksBtn.addEventListener("click", function () {
      const resultId = saveRemarksBtn.dataset.resultId;
      const originalLabel = saveRemarksBtn.querySelector(".btn-label").textContent;

      saveRemarksBtn.disabled = true;
      saveRemarksBtn.innerHTML = '<span class="btn-spinner"></span> Saving…';

      window.apiRequest("POST", `/api/admin/results/${resultId}/remarks`, {
        classTeacherRemark: classTeacherInput.value,
        principalRemark: principalInput.value,
      })
        .done(function (response) {
          if (!response || !response.success) return;
          if (classTeacherText) classTeacherText.textContent = response.classTeacherRemark || "";
          if (principalText) principalText.textContent = response.principalRemark || "";
          window.showToast("Remarks saved.", "success");
        })
        .always(function () {
          saveRemarksBtn.disabled = false;
          saveRemarksBtn.innerHTML = `<span class="btn-label">${originalLabel}</span>`;
        });
    });
  }
});

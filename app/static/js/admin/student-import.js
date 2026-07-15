/* ==========================================================================
   students-import.js — Bulk CSV import for student_import.html.
   This is the one exception to the JSON-only API rule in this project:
   file upload requires multipart/form-data, so we use a raw $.ajax call
   here instead of window.apiRequest, and attach the CSRF header manually.
   ========================================================================== */

$(function () {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  const fileInput = document.getElementById("csvFileInput");
  const selectedFileRow = document.getElementById("selectedFileRow");
  const fileNameLabel = document.getElementById("fileNameLabel");
  const removeFileBtn = document.getElementById("removeFileBtn");
  const confirmImportBtn = document.getElementById("confirmImportBtn");
  const resultsSection = document.getElementById("resultsSection");
  const importSummaryBar = document.getElementById("importSummaryBar");
  const skippedCard = document.getElementById("skippedCard");
  const skippedTableBody = document.getElementById("skippedTableBody");

  let selectedFile = null;

  ["dragover", "dragenter"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function () { dropzone.classList.remove("dragover"); });
  });
  dropzone.addEventListener("drop", function (e) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
  });

  removeFileBtn.addEventListener("click", function (e) {
    e.preventDefault();
    fileInput.value = "";
    selectedFile = null;
    selectedFileRow.style.display = "none";
    confirmImportBtn.disabled = true;
  });

  function handleFile(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      window.showToast("Please upload a .csv file.", "danger");
      return;
    }
    selectedFile = file;
    fileNameLabel.textContent = file.name;
    selectedFileRow.style.display = "";
    confirmImportBtn.disabled = false;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  confirmImportBtn.addEventListener("click", function () {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);

    confirmImportBtn.disabled = true;
    const spinner = confirmImportBtn.querySelector(".btn-spinner");
    if (spinner) spinner.style.display = "";

    $.ajax({
      method: "POST",
      url: "/api/students/import",
      data: formData,
      processData: false,
      contentType: false,
      headers: { "X-CSRFToken": $('meta[name="csrf-token"]').attr("content") },
    })
      .done(function (response) {
        if (!response || !response.success) return;

        resultsSection.style.display = "";
        importSummaryBar.innerHTML =
          '<span style="color: var(--color-success);"><strong>' + response.imported + "</strong> imported</span>" +
          '<span style="color: var(--color-danger);"><strong>' + response.skipped.length + "</strong> skipped</span>";

        skippedTableBody.innerHTML = "";
        if (response.skipped.length > 0) {
          skippedCard.style.display = "";
          response.skipped.forEach(function (row) {
            const tr = document.createElement("tr");
            tr.innerHTML =
              "<td>" + row.row + "</td>" +
              "<td>" + escapeHtml(row.reason) + "</td>";
            skippedTableBody.appendChild(tr);
          });
        } else {
          skippedCard.style.display = "none";
        }

        window.showToast(response.imported + " student(s) imported.", "success");
      })
      .fail(function (xhr) {
        const message = (xhr.responseJSON && xhr.responseJSON.message) || "Import failed. Please try again.";
        window.showToast(message, "danger");
      })
      .always(function () {
        confirmImportBtn.disabled = false;
        if (spinner) spinner.style.display = "none";
      });
  });
});
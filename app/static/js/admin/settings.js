/* ==========================================================================
   settings.js — School branding/contact settings, including logo upload.

   NOTE: this page does NOT use window.apiRequest() for saving, because
   logo upload requires multipart/form-data, not JSON. window.apiRequest
   hardcodes contentType: "application/json", so a raw $.ajax call is used
   here instead — the CSRF token still has to be attached manually.
   ========================================================================== */

$(function () {
  const $form = $("#settingsForm");
  const $saveBtn = $("#settingsSaveBtn");
  const $logoPreview = $("#logoPreview");
  const $logoInput = $("#logoInput");

  function loadSettings() {
    window.apiRequest("GET", "/api/settings").done(function (response) {
      if (!response || !response.success) return;
      $("#schoolName").val(response.schoolName);
      $("#address").val(response.address);
      $("#phone").val(response.phone);
      $("#email").val(response.email);
      $("#motto").val(response.motto);
      if (response.logoPath) {
        $logoPreview.attr("src", response.logoPath);
      }
    });
  }

  // Live preview of a newly chosen logo file before it's even saved
  $logoInput.on("change", function () {
    const file = this.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      $logoPreview.attr("src", e.target.result);
    };
    reader.readAsDataURL(file);
  });

  $form.on("submit", function (e) {
    e.preventDefault();

    const formData = new FormData();
    formData.append("schoolName", $("#schoolName").val().trim());
    formData.append("address", $("#address").val().trim());
    formData.append("phone", $("#phone").val().trim());
    formData.append("email", $("#email").val().trim());
    formData.append("motto", $("#motto").val().trim());

    const logoFile = $logoInput[0].files[0];
    if (logoFile) {
      formData.append("logo", logoFile);
    }

    $saveBtn.prop("disabled", true).find(".btn-spinner").show();

    $.ajax({
      method: "POST",
      url: "/api/settings",
      data: formData,
      processData: false,
      contentType: false,
      headers: { "X-CSRFToken": $('meta[name="csrf-token"]').attr("content") }
    })
      .done(function (response) {
        if (response && response.success) {
          window.showToast("Settings saved. Reloading to apply changes…", "success");
          setTimeout(function () { window.location.reload(); }, 800);
        }
      })
      .fail(function (xhr) {
        const message = (xhr.responseJSON && xhr.responseJSON.message) || "Something went wrong. Please try again.";
        window.showToast(message, "danger");
      })
      .always(function () {
        $saveBtn.prop("disabled", false).find(".btn-spinner").hide();
      });
  });

  loadSettings();
});

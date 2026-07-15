$(function () {
  const $script = $('script[src*="auth-login.js"]');
  const portal = $script.data("portal"); // "admin" | "teacher" | "portal"

  const $form = $("#authForm");
  const $errorBanner = $("#authErrorBanner");
  const $lockoutBanner = $("#authLockoutBanner");
  const $submitBtn = $("#authSubmitBtn");
  const $card = $("#authCard");

  let failedAttempts = 0;
  const LOCKOUT_THRESHOLD = 5; // client-side UX only — real throttling belongs server-side

  $form.on("submit", function (e) {
    e.preventDefault();

    if (failedAttempts >= LOCKOUT_THRESHOLD) {
      $lockoutBanner.prop("hidden", false);
      return;
    }

    $errorBanner.prop("hidden", true);
    $submitBtn.prop("disabled", true).find(".btn-spinner").show();

    const payload = portal === "portal"
      ? { admission_number: $("#fieldAdmissionNo").val().trim(), password: $("#fieldPassword").val() }
      : { email: $("#fieldEmail").val().trim(), password: $("#fieldPassword").val() };

    window.apiRequest("POST", "/auth/" + portal + "/login", payload)
      .done(function (response) {
        $submitBtn.prop("disabled", false).find(".btn-spinner").hide();
        if (response && response.success) {
          window.location.href = response.redirect_url;
        }
      })
      .fail(function (xhr) {
        $submitBtn.prop("disabled", false).find(".btn-spinner").hide();

        failedAttempts += 1;
        const message = (xhr.responseJSON && xhr.responseJSON.message) || "Incorrect credentials. Please try again.";
        $errorBanner.find("span").text(message);
        $errorBanner.prop("hidden", false);
        $card.addClass("shake");
        setTimeout(function () { $card.removeClass("shake"); }, 500);

        if (failedAttempts >= LOCKOUT_THRESHOLD) {
          $lockoutBanner.prop("hidden", false);
        }
      });
  });

  $("#forgotPasswordLink").on("click", function (e) {
    e.preventDefault();
    if (portal === "portal") {
      window.showToast("Please contact the school office to reset your password.", "info");
    } else {
      window.showToast("Contact the school administrator to reset your password.", "info");
    }
  });
});

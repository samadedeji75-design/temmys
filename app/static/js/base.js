/* ==========================================================================
   base.js — sidebar toggle, mobile nav, toast/flash helper, shared AJAX helper
   Loaded on every logged-in page. Keep this file framework-agnostic (jQuery
   only) and free of any page-specific logic.
   ========================================================================== */

$(function () {

  /* ---------------------------------------------------------------------
     Sidebar toggle (mobile off-canvas)
     ------------------------------------------------------------------- */
  function openSidebar() {
    $("body").addClass("sidebar-open");
  }
  function closeSidebar() {
    $("body").removeClass("sidebar-open");
  }

  $("#sidebarToggle").on("click", function () {
    $("body").hasClass("sidebar-open") ? closeSidebar() : openSidebar();
  });

  $("#sidebarBackdrop").on("click", closeSidebar);

  // Close sidebar automatically if window is resized back to desktop width
  $(window).on("resize", function () {
    if ($(window).width() > 991) closeSidebar();
  });

  /* ---------------------------------------------------------------------
     Flash message dismissal (server-rendered alerts)
     ------------------------------------------------------------------- */
  $(document).on("click", ".alert-close", function () {
    $(this).closest(".alert").fadeOut(150, function () { $(this).remove(); });
  });

  /* ---------------------------------------------------------------------
     Toast helper — window.showToast(message, category, autoDismissMs)
     category: 'success' | 'danger' | 'warning' | 'info'
     Used by every page-specific JS file instead of building alert markup
     by hand.
     ------------------------------------------------------------------- */
  const ICONS = {
    success: "bi-check-circle",
    danger: "bi-exclamation-octagon",
    warning: "bi-exclamation-triangle",
    info: "bi-info-circle"
  };

  window.showToast = function (message, category, autoDismissMs) {
    category = category || "info";
    autoDismissMs = autoDismissMs === undefined ? 4000 : autoDismissMs;

    const $alert = $(
      '<div class="alert alert-' + category + '" role="alert">' +
        '<i class="bi ' + (ICONS[category] || ICONS.info) + '"></i>' +
        "<span></span>" +
        '<button type="button" class="alert-close" aria-label="Dismiss">&times;</button>' +
      "</div>"
    );
    $alert.find("span").text(message);
    $("#flashContainer").append($alert);

    if (autoDismissMs > 0) {
      setTimeout(function () {
        $alert.fadeOut(150, function () { $(this).remove(); });
      }, autoDismissMs);
    }
    return $alert;
  };

  /* ---------------------------------------------------------------------
     Confirm modal helper — window.confirmAction({ title, body, confirmLabel,
     danger, onConfirm })
     Every destructive action across the app should route through this
     instead of a bare confirm().
     ------------------------------------------------------------------- */
  window.confirmAction = function (opts) {
    opts = opts || {};
    const $backdrop = $("#sharedConfirmModal");
    if ($backdrop.length === 0) {
      console.warn("confirmAction: #sharedConfirmModal not found on this page.");
      return;
    }
    $backdrop.find(".modal-box-header h3").text(opts.title || "Are you sure?");
    $backdrop.find(".modal-box-body").text(opts.body || "This action cannot be undone.");
    const $confirmBtn = $backdrop.find(".js-confirm-action-btn")
      .text(opts.confirmLabel || "Confirm")
      .toggleClass("btn-danger", !!opts.danger)
      .toggleClass("btn-primary", !opts.danger);

    $confirmBtn.off("click").on("click", function () {
      closeModal($backdrop);
      if (typeof opts.onConfirm === "function") opts.onConfirm();
    });

    openModal($backdrop);
  };

  /* ---------------------------------------------------------------------
     Generic modal open/close (used by confirmAction and page-specific
     add/edit modals — pages just need .modal-backdrop-custom + data attrs)
     ------------------------------------------------------------------- */
  function openModal($modal) { $modal.addClass("show"); }
  function closeModal($modal) { $modal.removeClass("show"); }
  window.openModal = openModal;
  window.closeModal = closeModal;

  $(document).on("click", "[data-modal-target]", function () {
    const target = $(this).data("modal-target");
    openModal($("#" + target));
  });

  $(document).on("click", ".modal-box-close, [data-modal-dismiss]", function () {
    closeModal($(this).closest(".modal-backdrop-custom"));
  });

  // Click on backdrop (outside modal box) closes it
  $(document).on("click", ".modal-backdrop-custom", function (e) {
    if (e.target === this) closeModal($(this));
  });

  /* ---------------------------------------------------------------------
     Shared AJAX helper — window.apiRequest(method, url, data)
     Wraps $.ajax with JSON in/out and consistent error toast handling.
     Page-specific JS files call this instead of raw $.ajax so every
     request gets the same error handling for free.
     ------------------------------------------------------------------- */
  window.apiRequest = function (method, url, data) {
    return $.ajax({
      method: method,
      url: url,
      data: data ? JSON.stringify(data) : undefined,
      contentType: "application/json",
      dataType: "json",
      headers: { "X-CSRFToken": $('meta[name="csrf-token"]').attr("content") }
    }).fail(function (xhr) {
      const message = (xhr.responseJSON && xhr.responseJSON.message) || "Something went wrong. Please try again.";
      window.showToast(message, "danger");
    });
  };

});
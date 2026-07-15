/* ==========================================================================
   class-roster.js — read-only per-class student roster (admin view).
   Reuses GET /api/students?classArmId=<id> — no dedicated endpoint.
   ========================================================================== */

$(function () {
  const $tbody = $("#rosterTableBody");
  if ($tbody.length === 0) return;

  const $table = $("#rosterTable").closest(".table-wrapper");
  const $empty = $("#rosterEmptyState");
  const armId = window.CLASS_ROSTER_ARM_ID;

  function render(students) {
    $tbody.empty();

    if (students.length === 0) {
      $table.hide();
      $empty.prop("hidden", false);
      return;
    }
    $table.show();
    $empty.prop("hidden", true);

    students.forEach(function (s) {
      const badgeClass = s.isActive ? "badge-success" : "badge-neutral";
      const badgeText = s.isActive ? "Active" : "Inactive";
      const $row = $(
        "<tr>" +
          "<td>" + $("<div>").text(s.fullName).html() + "</td>" +
          "<td>" + $("<div>").text(s.admissionNumber).html() + "</td>" +
          "<td>" + $("<div>").text(s.gender || "—").html() + "</td>" +
          "<td>" + $("<div>").text(s.guardianPhone || "—").html() + "</td>" +
          '<td><span class="badge ' + badgeClass + '">' + badgeText + "</span></td>" +
        "</tr>"
      );
      $tbody.append($row);
    });
  }

  window.apiRequest("GET", "/api/students?classArmId=" + armId).done(function (response) {
    if (response && response.success) render(response.students);
  });
});
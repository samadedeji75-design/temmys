/* ==========================================================================
   teacher-dashboard.js — teacher/dashboard.html, wired to the real API.
   ========================================================================== */

$(function () {
  const cardGrid = document.getElementById("teacherCardGrid");
  if (!cardGrid) return;

  const emptyState = document.getElementById("dashboardEmptyState");

  function render(assignments) {
    cardGrid.innerHTML = "";

    if (assignments.length === 0) {
      emptyState.style.display = "";
      return;
    }
    emptyState.style.display = "none";

    assignments.forEach(function (a) {
      const pct = a.studentsTotal === 0 ? 0 : Math.round((a.studentsWithScoresEntered / a.studentsTotal) * 100);
      const progressClass = pct >= 100 ? "complete" : pct === 0 ? "empty" : "partial";
      const href = "/teacher/classes/" + a.classArmId + "/subjects/" + a.subjectId + "/scores";

      const card = document.createElement("a");
      card.href = href;
      card.className = "assignment-card";
      card.innerHTML =
        "<div>" +
          '<div class="assignment-card-title">' + $("<div>").text(a.className).html() + "</div>" +
          '<div class="assignment-card-subtitle">' + $("<div>").text(a.subjectName).html() + "</div>" +
        "</div>" +
        '<div class="progress-row">' +
          '<div class="progress-track"><div class="progress-fill ' + progressClass + '" style="width:' + pct + '%;"></div></div>' +
          '<span class="progress-label">' + pct + "%</span>" +
        "</div>" +
        '<div class="assignment-card-footer">' +
          "<span>" + a.studentsWithScoresEntered + " / " + a.studentsTotal + " entered</span>" +
          '<span><i class="bi bi-arrow-right"></i></span>' +
        "</div>";
      cardGrid.appendChild(card);
    });
  }

  function renderClassRemarksLinks(assignments) {
    const section = document.getElementById("classRemarksSection");
    const container = document.getElementById("classRemarksLinks");
    if (!section || !container) return;

    // One link per distinct class arm — a teacher assigned to several
    // subjects in the same class would otherwise see the class repeated.
    const seen = new Set();
    const classes = [];
    assignments.forEach(function (a) {
      if (seen.has(a.classArmId)) return;
      seen.add(a.classArmId);
      classes.push(a);
    });

    if (classes.length === 0) {
      section.style.display = "none";
      return;
    }
    section.style.display = "";
    container.innerHTML = "";

    classes.forEach(function (a) {
      const card = document.createElement("a");
      card.href = "/teacher/classes/" + a.classArmId + "/remarks";
      card.className = "assignment-card";
      card.innerHTML =
        "<div>" +
          '<div class="assignment-card-title">' + $("<div>").text(a.className).html() + "</div>" +
          '<div class="assignment-card-subtitle">Enter remarks for this class</div>' +
        "</div>" +
        '<div class="assignment-card-footer">' +
          "<span></span>" +
          '<span><i class="bi bi-arrow-right"></i></span>' +
        "</div>";
      container.appendChild(card);
    });
  }

  window.apiRequest("GET", "/api/teacher/my-assignments").done(function (response) {
    if (response && response.success) {
      render(response.assignments);
      renderClassRemarksLinks(response.assignments);
    }
  });
});
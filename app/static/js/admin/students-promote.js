/* students-promote.js
   Bulk-move students from one class arm to another.
   Uses GET /api/classes, GET /api/students?classArmId=<id> and
   POST /api/students/promote. */

$(function () {
  "use strict";

  const fromSelect = document.getElementById("promoteFrom");
  if (!fromSelect) return;

  const toSelect = document.getElementById("promoteTo");
  const promoteBtn = document.getElementById("promoteBtn");
  const toolbar = document.getElementById("promoteToolbar");
  const selectAll = document.getElementById("promoteSelectAll");
  const countLabel = document.getElementById("promoteCount");
  const tableWrap = document.getElementById("promoteTableWrap");
  const tableBody = document.getElementById("promoteTableBody");
  const emptyState = document.getElementById("promoteEmpty");

  let arms = [];      // [{id, label}] in level order
  let students = [];  // active students of the chosen class

  function selectedIds() {
    return Array.from(tableBody.querySelectorAll("input[type=checkbox]:checked")).map(function (box) {
      return Number(box.value);
    });
  }

  function armLabel(id) {
    const arm = arms.find(function (a) { return a.id === Number(id); });
    return arm ? arm.label : "";
  }

  function updateControls() {
    const count = selectedIds().length;
    countLabel.textContent = count + " selected";
    selectAll.checked = students.length > 0 && count === students.length;
    promoteBtn.disabled = !(count > 0 && toSelect.value);
  }

  function fillPickers() {
    fromSelect.length = 1;
    arms.forEach(function (arm) {
      const option = document.createElement("option");
      option.value = arm.id;
      option.textContent = arm.label;
      fromSelect.appendChild(option);
    });
  }

  function fillTargets() {
    toSelect.length = 1;
    arms.forEach(function (arm) {
      if (String(arm.id) === fromSelect.value) return;
      const option = document.createElement("option");
      option.value = arm.id;
      option.textContent = arm.label;
      toSelect.appendChild(option);
    });
    toSelect.disabled = !fromSelect.value;
  }

  function renderStudents() {
    tableBody.replaceChildren();

    if (!fromSelect.value) {
      toolbar.hidden = true;
      tableWrap.hidden = true;
      emptyState.hidden = false;
      return;
    }

    if (students.length === 0) {
      toolbar.hidden = true;
      tableWrap.hidden = true;
      emptyState.hidden = false;
      emptyState.querySelector("h3").textContent = "No active students in this class";
      updateControls();
      return;
    }

    emptyState.hidden = true;
    toolbar.hidden = false;
    tableWrap.hidden = false;

    students.forEach(function (s) {
      const row = document.createElement("tr");

      const boxCell = document.createElement("td");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = s.id;
      box.addEventListener("change", updateControls);
      boxCell.appendChild(box);
      row.appendChild(boxCell);

      const nameCell = document.createElement("td");
      nameCell.style.fontWeight = "600";
      nameCell.textContent = s.fullName;
      row.appendChild(nameCell);

      const admCell = document.createElement("td");
      admCell.className = "cell-muted";
      admCell.textContent = s.admissionNumber;
      row.appendChild(admCell);

      tableBody.appendChild(row);
    });

    updateControls();
  }

  function loadStudents() {
    students = [];
    if (!fromSelect.value) {
      renderStudents();
      return;
    }
    window.apiRequest("GET", "/api/students?classArmId=" + encodeURIComponent(fromSelect.value)).done(function (response) {
      if (!response || !response.success) return;
      students = response.students.filter(function (s) { return s.isActive; });
      renderStudents();
    });
  }

  fromSelect.addEventListener("change", function () {
    fillTargets();
    loadStudents();
  });
  toSelect.addEventListener("change", updateControls);

  selectAll.addEventListener("change", function () {
    tableBody.querySelectorAll("input[type=checkbox]").forEach(function (box) {
      box.checked = selectAll.checked;
    });
    updateControls();
  });

  promoteBtn.addEventListener("click", function () {
    const ids = selectedIds();
    if (!ids.length || !toSelect.value) return;

    const message = "Move " + ids.length + " student(s) from " + armLabel(fromSelect.value) +
      " to " + armLabel(toSelect.value) + "?";
    if (!window.confirm(message)) return;

    promoteBtn.disabled = true;
    window.apiRequest("POST", "/api/students/promote", {
      studentIds: ids,
      targetClassArmId: Number(toSelect.value)
    }).done(function (response) {
      if (response && response.success) {
        window.showToast(response.message, "success");
        loadStudents();
      }
    }).always(function () {
      updateControls();
    });
  });

  window.apiRequest("GET", "/api/classes").done(function (response) {
    if (!response || !response.success) return;
    const levels = response.levels.slice().sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
    arms = [];
    levels.forEach(function (level) {
      response.arms
        .filter(function (arm) { return arm.levelId === level.id; })
        .sort(function (a, b) { return a.name.localeCompare(b.name); })
        .forEach(function (arm) {
          arms.push({ id: arm.id, label: level.name + " " + arm.name });
        });
    });
    fillPickers();
    fillTargets();
  });
});

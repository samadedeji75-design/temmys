/* portal-dashboard.js
   Interactive part of portal/dashboard.html: summary cards, a trend chart
   across terms, a term switcher and a subject breakdown with change since
   the previous term. Data comes from GET /api/portal/dashboard.
   The result history cards and identity header are still handled by
   portal.js, so this file only touches the #insights section. */

$(function () {
  "use strict";

  const insights = document.getElementById("insights");
  if (!insights) return;

  const summaryEl = document.getElementById("pdSummary");
  const pillsEl = document.getElementById("pdPills");
  const detailEl = document.getElementById("pdDetail");
  const chartWrap = document.getElementById("pdChartWrap");
  const chartCanvas = document.getElementById("pdTrendChart");

  let terms = [];
  let selected = 0;
  let trendChart = null;

  /* ---------------------------------------------------------------- helpers */

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function ordinal(n) {
    const v = n % 100;
    if (v >= 11 && v <= 13) return n + "th";
    switch (n % 10) {
      case 1: return n + "st";
      case 2: return n + "nd";
      case 3: return n + "rd";
      default: return n + "th";
    }
  }

  function tone(score) {
    if (score >= 70) return "good";
    if (score >= 50) return "ok";
    if (score >= 40) return "low";
    return "poor";
  }

  function shortLabel(t) {
    return t.termLabel + " " + t.sessionLabel;
  }

  function round1(n) {
    return Math.round(n * 10) / 10;
  }

  function deltaNode(diff) {
    if (diff === null) return el("span", "pd-delta pd-delta-none", "");
    if (diff > 0) return el("span", "pd-delta pd-delta-up", "\u25B2 +" + diff);
    if (diff < 0) return el("span", "pd-delta pd-delta-down", "\u25BC " + diff);
    return el("span", "pd-delta pd-delta-none", "no change");
  }

  /* --------------------------------------------------------- summary cards */

  function addSummaryCard(label, value, subNode) {
    const card = el("div", "pd-stat");
    card.appendChild(el("div", "pd-stat-label", label));
    card.appendChild(el("div", "pd-stat-value", value));
    if (subNode) card.appendChild(subNode);
    summaryEl.appendChild(card);
  }

  function renderSummary() {
    const latest = terms[terms.length - 1];
    const prev = terms.length > 1 ? terms[terms.length - 2] : null;

    summaryEl.replaceChildren();

    let sub = null;
    if (prev) {
      sub = el("div", "pd-stat-sub");
      sub.appendChild(deltaNode(round1(latest.termAverage - prev.termAverage)));
      sub.appendChild(document.createTextNode(" vs last term"));
    }
    addSummaryCard("Latest term average", latest.termAverage + "%", sub);

    addSummaryCard("Overall grade", latest.grade || "-", el("div", "pd-stat-sub", latest.termLabel));

    const positionText = latest.position ? ordinal(latest.position) + " of " + latest.classSize : "-";
    addSummaryCard(
      latest.isSessionCumulative ? "Position (whole session)" : "Position in class",
      positionText,
      null
    );

    addSummaryCard("Terms on record", String(terms.length), null);
  }

  /* ------------------------------------------------------------ trend chart */

  function pointColors() {
    return terms.map(function (_, i) { return i === selected ? "#0B2E59" : "#1D6FB8"; });
  }

  function renderTrend() {
    if (!chartCanvas || !window.Chart) {
      if (chartWrap) chartWrap.hidden = true;
      return;
    }

    trendChart = new window.Chart(chartCanvas, {
      type: "line",
      data: {
        labels: terms.map(shortLabel),
        datasets: [{
          label: "Term average",
          data: terms.map(function (t) { return t.termAverage; }),
          borderColor: "#1D6FB8",
          backgroundColor: "rgba(29, 111, 184, 0.12)",
          fill: true,
          tension: 0.3,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: pointColors()
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; } } }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) { return "Average: " + ctx.parsed.y + "%"; }
            }
          }
        },
        onClick: function (evt, elements) {
          if (elements && elements.length) selectTerm(elements[0].index);
        }
      }
    });
  }

  function refreshTrendHighlight() {
    if (!trendChart) return;
    trendChart.data.datasets[0].pointBackgroundColor = pointColors();
    trendChart.update("none");
  }

  /* ------------------------------------------------------------------ pills */

  function renderPills() {
    pillsEl.replaceChildren();
    terms.forEach(function (t, i) {
      const btn = el("button", "pd-pill" + (i === selected ? " active" : ""), t.termLabel + " \u00B7 " + t.sessionLabel);
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", i === selected ? "true" : "false");
      btn.addEventListener("click", function () { selectTerm(i); });
      pillsEl.appendChild(btn);
    });
  }

  /* ----------------------------------------------------------------- detail */

  function previousTotals(index) {
    const map = {};
    if (index > 0) {
      terms[index - 1].subjects.forEach(function (s) { map[s.name] = s.total; });
    }
    return map;
  }

  function addFact(parent, label, value) {
    const box = el("div", "pd-fact");
    box.appendChild(el("div", "pd-fact-label", label));
    box.appendChild(el("div", "pd-fact-value", value));
    parent.appendChild(box);
  }

  function renderDetail() {
    const t = terms[selected];
    const prevTotals = previousTotals(selected);

    detailEl.replaceChildren();

    /* header with actions */
    const head = el("div", "pd-detail-head");
    head.appendChild(el("h3", "pd-detail-title", t.termLabel + " \u00B7 " + t.sessionLabel + " Session"));
    const actions = el("div", "pd-actions");
    const view = el("a", "btn btn-primary btn-sm", "View full result");
    view.href = "/portal/results/" + t.resultId;
    const pdf = el("a", "btn btn-secondary btn-sm", "Download PDF");
    pdf.href = "/portal/results/" + t.resultId + "/pdf";
    actions.appendChild(view);
    actions.appendChild(pdf);
    head.appendChild(actions);
    detailEl.appendChild(head);

    /* quick facts */
    const facts = el("div", "pd-facts");
    addFact(facts, "Term average", t.termAverage + "%");
    if (t.isSessionCumulative) addFact(facts, "Session average", t.average + "%");
    addFact(facts, "Grade", t.grade || "-");
    addFact(facts, t.isSessionCumulative ? "Session position" : "Position", t.position ? ordinal(t.position) + " of " + t.classSize : "-");
    detailEl.appendChild(facts);

    /* subjects */
    if (!t.subjects.length) {
      detailEl.appendChild(el("p", "pd-empty", "Subject scores are not available for this term."));
    } else {
      if (t.subjects.length >= 2) {
        const ranked = t.subjects.slice().sort(function (a, b) { return b.total - a.total; });
        const best = ranked[0];
        const weakest = ranked[ranked.length - 1];
        const highlights = el("div", "pd-highlights");
        highlights.appendChild(el("span", "pd-highlight pd-highlight-good", "Strongest: " + best.name + " (" + best.total + ")"));
        highlights.appendChild(el("span", "pd-highlight pd-highlight-low", "Needs attention: " + weakest.name + " (" + weakest.total + ")"));
        detailEl.appendChild(highlights);
      }

      const list = el("div", "pd-subjects");
      t.subjects.forEach(function (s) {
        const row = el("div", "pd-subject");

        const top = el("div", "pd-subject-top");
        top.appendChild(el("span", "pd-subject-name", s.name));
        const right = el("span", "pd-subject-right");
        const prevTotal = prevTotals[s.name];
        right.appendChild(deltaNode(prevTotal === undefined ? null : round1(s.total - prevTotal)));
        right.appendChild(el("span", "pd-subject-score", String(s.total)));
        right.appendChild(el("span", "pd-chip pd-chip-" + tone(s.total), s.grade || "-"));
        top.appendChild(right);
        row.appendChild(top);

        const bar = el("div", "pd-bar");
        const fill = el("div", "pd-bar-fill pd-tone-" + tone(s.total));
        fill.style.width = Math.max(0, Math.min(100, s.total)) + "%";
        bar.appendChild(fill);
        row.appendChild(bar);

        row.appendChild(el("div", "pd-subject-meta", "CA " + s.ca + " \u00B7 Exam " + s.exam + (s.remark ? " \u00B7 " + s.remark : "")));
        list.appendChild(row);
      });
      detailEl.appendChild(list);
    }

    /* remarks */
    if (t.classTeacherRemark) {
      const box = el("div", "pd-remark");
      box.appendChild(el("div", "pd-remark-label", "Class teacher's remark"));
      box.appendChild(el("p", "pd-remark-text", t.classTeacherRemark));
      detailEl.appendChild(box);
    }
    if (t.principalRemark) {
      const box = el("div", "pd-remark");
      box.appendChild(el("div", "pd-remark-label", "Principal's remark"));
      box.appendChild(el("p", "pd-remark-text", t.principalRemark));
      detailEl.appendChild(box);
    }
  }

  /* -------------------------------------------------------------- selection */

  function selectTerm(index) {
    if (index < 0 || index >= terms.length) return;
    selected = index;
    renderPills();
    renderDetail();
    refreshTrendHighlight();
  }

  /* ------------------------------------------------------------------- init */

  window.apiRequest("GET", "/api/portal/dashboard").done(function (response) {
    if (!response || !response.success || !response.terms || response.terms.length === 0) return;

    terms = response.terms;
    selected = terms.length - 1;

    insights.hidden = false;
    renderSummary();
    renderTrend();
    renderPills();
    renderDetail();
  });
});

# UI Specification — File Structure & Page Content

Covers every screen across the three portals (Admin, Teacher, Parent/Student), the exact file names, and what each page must display. Follows the SceneX pattern: dark-themed base, Bootstrap 5 grid, jQuery for interactivity, fixed sidebar for logged-in views, no page-specific CSS unless a page truly needs it (prefer shared component classes).

---

## Folder Structure

```
/static
  /css
    base.css              -> resets, CSS variables, typography, shared layout (sidebar, navbar, buttons, cards)
    auth.css               -> login pages (all three portals share this)
    admin.css               -> admin-only layout tweaks (tables, CRUD modals)
    teacher.css              -> score entry grid styling
    portal.css               -> parent/student result view + print styles
    result-sheet.css          -> the printable/PDF-mirrored result layout (shared by portal view and print)
  /js
    base.js                 -> sidebar toggle, mobile nav, shared AJAX helpers, toast/alert helper
    admin
      admin-dashboard.js
      students.js            -> student CRUD table (add/edit/delete modals, CSV import)
      teachers.js             -> teacher CRUD + assignment modal
      classes.js               -> class level/arm CRUD
      subjects.js               -> subject CRUD + class-subject assignment
      grading-scale.js           -> grading band CRUD
      sessions-terms.js            -> session/term CRUD, active toggle, lock toggle
      finalize-term.js               -> finalization screen logic, completion status polling
    teacher
      teacher-dashboard.js
      score-entry.js           -> live CA/exam total + grade calc, inline save, validation
    portal
      portal-dashboard.js
      result-view.js            -> fetch/render result, download trigger
  /images
    logo.png, favicon.ico, placeholder-avatar.png

/templates
  /shared
    base.html                -> master layout, block content, loads base.css + base.js
    navbar.html               -> included in base, differs by role via a `role` variable
    sidebar.html                -> included in base, links differ by role
    footer.html
    _flash_messages.html
    _pagination.html
  /auth
    admin_login.html
    teacher_login.html
    portal_login.html
  /admin
    dashboard.html
    students_list.html
    student_form.html          -> add/edit (reused, mode passed in)
    student_import.html         -> CSV bulk upload
    teachers_list.html
    teacher_form.html
    teacher_assignments.html      -> assign subjects/classes to a teacher
    classes_list.html
    class_form.html
    subjects_list.html
    subject_form.html
    class_subjects.html           -> assign subjects to a class arm
    grading_scale.html
    sessions_terms.html
    finalize_term.html
    class_result_overview.html      -> admin view of a class's finalized results / batch print
  /teacher
    dashboard.html
    class_subject_students.html    -> student list for a (class, subject) pair
    score_entry.html
  /portal
    dashboard.html
    result_view.html
    result_print.html            -> stripped-down template used only for PDF/print rendering
```

Naming convention: lowercase, underscores, matches the route name it renders. JS files are named after the page they control, one file per page, nothing shared unless it's genuinely reused (`base.js`).

---

## Shared Layout Elements (all logged-in pages)

- **Sidebar** (fixed, collapses to hamburger on mobile — same pattern as SceneX): role-specific nav links, school logo at top, active session/term indicator, logout link at bottom
- **Top navbar**: page title, logged-in user's name + avatar initial, quick logout icon on mobile
- **Flash messages**: dismissible Bootstrap alerts for success/error feedback, triggered after every form action
- **Footer**: school name, current session/term, small print

---

## AUTH PAGES (public, no sidebar)

### `admin_login.html` / `teacher_login.html` / `portal_login.html`
- Centered card: school logo, "Sign in" heading specific to the portal (e.g. "Parent/Student Login")
- Portal login: fields are **Admission Number** + **Password** (not name — collisions and it's not secret)
- Admin/Teacher login: **Email** + **Password**
- "Forgot password?" link (admin-reset flow for portal, standard reset for teacher/admin)
- Error state: invalid credentials message shown inline, no page reload (AJAX submit via jQuery)
- Rate-limit lockout message if too many attempts

---

## ADMIN PAGES

### `dashboard.html`
- Stat cards: total students, total teachers, active classes, active session/term
- Term finalization status widget: how many classes are fully finalized vs pending
- Quick links: Add Student, Add Teacher, Manage Grading Scale
- Recent activity feed (last 10 score edits or admin actions, if logging is in place)

### `students_list.html`
- Filterable/searchable table: Name, Admission No., Class, Guardian, Status (active/inactive)
- Filters: by class arm, by session
- Row actions: Edit, Deactivate, Reset Password, View Result History
- "Add Student" and "Bulk Import (CSV)" buttons top-right
- Pagination

### `student_form.html`
- Fields: Full Name, Admission Number, Gender, DOB, Class Arm (dropdown), Guardian Name/Phone/Email, initial portal password (auto-generate button + manual override)
- Save / Cancel buttons, inline validation (required fields, admission number uniqueness checked via AJAX before submit)

### `student_import.html`
- File upload input (CSV only), template download link ("Download sample CSV format")
- Preview table of parsed rows before committing (client-side parse via jQuery/PapaParse-style, or server round-trip preview)
- Row-level error flags (duplicate admission number, missing class arm) before final "Confirm Import"

### `teachers_list.html`
- Table: Name, Email, Assigned Classes/Subjects count, Status
- Row actions: Edit, Deactivate, Manage Assignments, Reset Password
- "Add Teacher" button

### `teacher_form.html`
- Fields: Full Name, Email, initial password
- Save / Cancel

### `teacher_assignments.html`
- Two-column assignment builder: pick Class Arm → pick Subject(s) offered by that class → assign to this teacher
- Table below showing this teacher's current assignments with remove (x) buttons per row

### `classes_list.html`
- Grouped display: Class Level → its Arms (e.g. "SS1" expandable to show "Gold", "Diamond")
- Student count per arm
- Add Class Level / Add Arm buttons, edit/delete per row

### `class_form.html`
- Simple form: Level name + order (for class levels), or Arm name + parent level (for arms)

### `subjects_list.html`
- Simple table: Subject Name, Code
- Add/Edit/Delete inline

### `class_subjects.html`
- Pick a Class Arm → checklist of all subjects → check which ones this class offers → Save
- Shows current subject count for that class

### `grading_scale.html`
- Editable table: Min Score, Max Score, Grade, Remark — add row / delete row / inline edit
- Validation: ranges shouldn't overlap or leave gaps (flagged visually, not silently allowed)
- Shows CA Max / Exam Max config fields (from `SchoolConfig`) at the top of the same page

### `sessions_terms.html`
- Sessions listed with their terms nested underneath
- "Set Active" toggle per session/term (only one can be active at a time — enforced)
- Lock/Unlock toggle per term
- Add Session, Add Term buttons

### `finalize_term.html`
- Class-by-class breakdown: X of Y students have complete scores
- Per-class "Finalize" button (disabled until 100% complete, or allows override with a confirmation warning listing incomplete students)
- After finalizing: shows computed class positions summary, link to `class_result_overview.html`

### `class_result_overview.html`
- Read-only table: every student in the class, cumulative average, grade, position — sorted by position
- "Download Class Result (Batch PDF)" button
- Per-student "View/Download Individual Result" link

---

## TEACHER PAGES

### `dashboard.html`
- List of assigned (Class, Subject) pairs as clickable cards, for the currently active term only
- Each card shows: class name, subject name, how many students have scores entered vs total (progress indicator)

### `class_subject_students.html`
- Table of students in that class for that subject: Name, Admission No., current CA/Exam status (entered / missing)
- Click a student row → opens `score_entry.html` for that student, or inline-expandable row (decide based on whether you want per-student pages or one big editable table — recommend one editable table for the whole class, faster for teachers than clicking into 40 individual pages)

### `score_entry.html`
*(or this becomes the same page as above if using the single-table approach — recommended)*
- Editable table: one row per student — Name | CA1 | CA2 | CA3 | Exam | CA Total (auto) | Subject Total (auto) | Grade (auto)
- Auto-calculated columns update live via jQuery as the teacher types, no page reload
- Max-score validation shown inline (red border + tooltip if a score exceeds configured max)
- "Save All" button, with per-row saved/unsaved indicator (small dot or checkmark)
- Locked-term banner if the term is locked: fields become read-only, message explains why

---

## PARENT/STUDENT PORTAL PAGES

### `dashboard.html`
- Student's name, class, admission number displayed top of page (confirms correct login)
- List of terms/sessions with results available, only ones marked finalized — shown as cards ("First Term 2025/2026 — View Result")
- If no finalized results yet: friendly empty state ("Your child's result for this term isn't published yet")

### `result_view.html`
- Header: school logo, student name, admission number, class, session/term
- Full subject table: Subject | CA1 | CA2 | CA3 | CA Total | Exam | Subject Total | Grade | Remark
- Summary block: Cumulative Total, Cumulative Average, Overall Grade, Class Position (e.g. "5th out of 32")
- Class Teacher's Remark, Principal's Remark (text blocks)
- "Download PDF" button (triggers server-side ReportLab generation)

### `result_print.html`
- Same content as `result_view.html` but stripped of navbar/sidebar/buttons, styled purely for print/PDF conversion, matches the letterhead layout used in the actual PDF output (so on-screen preview and downloaded PDF look consistent, no surprises)

---

## CSS Approach

- `base.css` defines CSS custom properties (`--primary-color`, `--sidebar-width`, `--font-size-base` in rem, etc.) matching the pattern already established in SceneX
- Dark theme by default, consistent with SceneX's established look, unless the school wants a lighter "official document" feel for the portal specifically (worth asking, since parents expect result pages to look formal, not like a nightlife app — recommend keeping the portal's `result_view.html` closer to a clean white/light card even if the rest of the dashboard is dark, results are a document, not a social feed)
- `result-sheet.css` is deliberately separate and print-optimized: white background, black text, table borders, no shadows/gradients, `@media print` rules to hide anything non-essential

## JS Approach

- No page loads a JS file it doesn't need — `score_entry.html` only loads `base.js` + `score-entry.js`, not the entire admin JS bundle
- All CRUD actions (add/edit/delete rows) go through AJAX (`$.ajax` / `$.post`) with JSON responses, table updates in place without full page reloads, matching the jQuery conventions already used in SceneX (`.on()`, `.hasClass()`, `.data()`)
- Every destructive action (delete student, deactivate teacher, remove assignment) triggers a confirm modal before firing the request, never a bare `confirm()` browser dialog

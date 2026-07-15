# No server-rendered CRUD forms needed here — the admin CRUD screens
# (sessions/terms, classes, subjects, grading scale) submit via AJAX to
# app/api/routes.py as JSON, per the pattern already built into the
# static/js/admin/*.js files. This file is intentionally left without
# form classes; keep it only if a future page needs a real server-rendered
# form (e.g. student CSV import in Phase 3 might).

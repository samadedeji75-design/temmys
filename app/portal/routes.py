from flask import render_template, session, abort, send_file

from app.models import StudentTermResult
from app.portal import portal_bp
from app.portal.decorators import portal_required


@portal_bp.route("/dashboard")
@portal_required
def dashboard():
    return render_template("portal/dashboard.html", role="student", active_page="dashboard")


@portal_bp.route("/results/<int:result_id>")
@portal_required
def result_view(result_id):
    from app.services.results import build_result_context
    result = StudentTermResult.query.get_or_404(result_id)
    if result.student_id != session["studentonline"]:
        abort(403)
    if result.status != "finalized":
        abort(404)
    context = build_result_context(result)
    return render_template("portal/result_view.html", role="student", active_page="results", **context)


@portal_bp.route("/results/<int:result_id>/print")
@portal_required
def result_print(result_id):
    from app.services.results import build_result_context
    result = StudentTermResult.query.get_or_404(result_id)
    if result.student_id != session["studentonline"]:
        abort(403)
    if result.status != "finalized":
        abort(404)
    context = build_result_context(result)
    return render_template("portal/result_print.html", **context)


@portal_bp.route("/results/<int:result_id>/pdf")
@portal_required
def result_pdf(result_id):
    from app.services.pdf import build_single_result_pdf

    result = StudentTermResult.query.get_or_404(result_id)
    if result.student_id != session["studentonline"]:
        abort(403)
    if result.status != "finalized":
        abort(404)

    pdf_buffer = build_single_result_pdf(result)
    filename = f"{result.student.admission_number}_{result.term.name}_{result.session.name}.pdf".replace(" ", "_")
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)

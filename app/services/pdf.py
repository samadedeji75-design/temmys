"""
app/services/pdf.py

ReportLab PDF generation for the student result document (Phase 7), plus
the student login-credentials export (added alongside the teacher-email
feature).

Built entirely on top of app.services.results.build_result_context() —
this module does not independently re-query Score/ClassSubject/etc.
Content must match shared/_result_document.html field-for-field.

No QR code / verification feature (descoped, see PHASE_7_HANDOFF §1.2).
No signature line (removed from the HTML in §1.1; not present here either).
"""

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
)

from app.models import SchoolConfig
from app.services.results import build_result_context


_styles = getSampleStyleSheet()

_school_name_style = ParagraphStyle(
    "SchoolName", parent=_styles["Title"], fontSize=16, alignment=TA_CENTER, spaceAfter=2,
)
_school_meta_style = ParagraphStyle(
    "SchoolMeta", parent=_styles["Normal"], fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor("#555555"),
)
_doc_title_style = ParagraphStyle(
    "DocTitle", parent=_styles["Heading2"], fontSize=12, alignment=TA_CENTER, spaceBefore=8, spaceAfter=2,
)
_term_line_style = ParagraphStyle(
    "TermLine", parent=_styles["Normal"], fontSize=9.5, alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=10,
)
_section_label_style = ParagraphStyle(
    "SectionLabel", parent=_styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#666666"),
)
_footer_style = ParagraphStyle(
    "Footer", parent=_styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#888888"), spaceBefore=12,
)


def _dash_if_none(value):
    return "—" if value is None else value


def _build_result_flowables(result, school_config, ca_max, exam_max):
    """Returns the ReportLab flowables for one student's report page.
    Shared by build_single_result_pdf and build_batch_result_pdf so both
    outputs are pixel-identical for the same student."""

    context = build_result_context(result)
    student = context["student"]
    class_arm = context["class_arm"]
    term = context["term"]
    sess = context["session"]
    class_size = context["class_size"]
    subject_rows = context["subject_rows"]

    flow = []

    # -- Header --------------------------------------------------------
    logo_path = school_config.logo_path if school_config else None
    if logo_path:
        # logo_path is stored as a web path (e.g. "/static/uploads/logos/x.jpg");
        # resolve it against the app's static folder on disk.
        try:
            from flask import current_app
            fs_path = os.path.join(current_app.root_path, logo_path.lstrip("/"))
            if os.path.isfile(fs_path):
                img = Image(fs_path, width=22 * mm, height=22 * mm)
                img.hAlign = "CENTER"
                flow.append(img)
        except Exception:
            # Never let a bad/missing logo crash a whole (possibly batch) PDF.
            pass

    school_name = school_config.school_name if school_config else ""
    address = (school_config.address if school_config else "") or ""

    flow.append(Paragraph(school_name, _school_name_style))
    if address:
        flow.append(Paragraph(address, _school_meta_style))

    rule_table = Table([[""]], colWidths=["100%"], rowHeights=[1])
    rule_table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#111111"))]))
    flow.append(Spacer(1, 4))
    flow.append(rule_table)

    flow.append(Paragraph("STUDENT TERMINAL REPORT SHEET", _doc_title_style))
    flow.append(Paragraph(f"{term.name} — {sess.name} Session", _term_line_style))

    # -- Student info ----------------------------------------------------
    info_rows = [
        ["Student Name", student.full_name, "Admission No.", student.admission_number],
        ["Class", class_arm.display_name, "Position in Class",
         f"{_dash_if_none(result.class_position)} of {class_size}"],
        ["Gender", _dash_if_none(student.gender), "", ""],
    ]
    info_table = Table(info_rows, colWidths=["22%", "28%", "22%", "28%"])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#666666")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#666666")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(Spacer(1, 8))
    flow.append(info_table)
    flow.append(Spacer(1, 10))

    # -- Subject table -----------------------------------------------------
    header = ["Subject", "CA1", "CA2", "CA3", f"CA Total\n/{ca_max}", f"Exam\n/{exam_max}",
              f"Total\n/{ca_max + exam_max}", "Grade", "Remark"]
    table_data = [header]
    for row in subject_rows:
        table_data.append([
            row["subject_name"],
            _dash_if_none(row["ca1"]),
            _dash_if_none(row["ca2"]),
            _dash_if_none(row["ca3"]),
            _dash_if_none(row["ca_total"]),
            _dash_if_none(row["exam_score"]),
            _dash_if_none(row["subject_total"]),
            row["grade"] or "—",
            row["remark"] or "—",
        ])

    subject_table = Table(
        table_data,
        colWidths=[32 * mm, 12 * mm, 12 * mm, 12 * mm, 18 * mm, 16 * mm, 16 * mm, 14 * mm, 28 * mm],
        repeatRows=1,
    )
    subject_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-2, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (-1, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(subject_table)
    flow.append(Spacer(1, 10))

    # -- Summary -------------------------------------------------------
    max_total = (ca_max + exam_max) * len(subject_rows)
    summary_rows = [
        ["Cumulative Total", f"{result.cumulative_total} / {max_total}",
         "Average", f"{result.cumulative_average}%"],
        ["Overall Grade", _dash_if_none(result.overall_grade),
         "Class Position", f"{_dash_if_none(result.class_position)} of {class_size}"],
    ]
    summary_table = Table(summary_rows, colWidths=["22%", "28%", "22%", "28%"])
    summary_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#666666")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#666666")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(summary_table)
    flow.append(Spacer(1, 12))

    # -- Remarks (no signature line — see PHASE_7_HANDOFF §1.1) -------------
    remark_rows = [
        [Paragraph("Class Teacher's Remark", _section_label_style),
         Paragraph("Principal's Remark", _section_label_style)],
        [Paragraph(result.class_teacher_remark or "", _styles["Normal"]),
         Paragraph(result.principal_remark or "", _styles["Normal"])],
    ]
    remark_table = Table(remark_rows, colWidths=["50%", "50%"])
    remark_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
    ]))
    flow.append(remark_table)

    # -- Footer ----------------------------------------------------------
    current_year = datetime.utcnow().year
    flow.append(Paragraph(f"Generated on {current_year} · {school_name} Result Management System", _footer_style))

    return flow


def safe_filename(name):
    """Strip characters that break Content-Disposition download names or
    get misread as path separators by the browser — spaces, slashes, and
    backslashes. Session names in particular are stored like "2025/2026",
    which would otherwise land a literal "/" in the filename."""
    for ch in (" ", "/", "\\"):
        name = name.replace(ch, "_")
    return name


def build_single_result_pdf(result):
    """One StudentTermResult -> one PDF, single student, one or more pages
    if the subject table is long. `result` must already be the finalized
    row the caller has verified ownership/status on — this function does
    no authorization or status checking itself."""

    school_config = SchoolConfig.query.first()
    ca_max = school_config.ca_max_score if school_config else 40
    exam_max = school_config.exam_max_score if school_config else 60

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )
    flowables = _build_result_flowables(result, school_config, ca_max, exam_max)
    doc.build(flowables)
    buffer.seek(0)
    return buffer


def build_batch_result_pdf(results):
    """List of StudentTermResult rows (already filtered to one class arm,
    status == 'finalized', ordered by class_position by the caller) -> one
    combined PDF, one student's report per page. Calls the same per-student
    flowable-building logic as build_single_result_pdf so the batch output
    and single-download output are pixel-identical for the same student."""

    school_config = SchoolConfig.query.first()
    ca_max = school_config.ca_max_score if school_config else 40
    exam_max = school_config.exam_max_score if school_config else 60

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )

    flowables = []
    for i, result in enumerate(results):
        if i > 0:
            flowables.append(PageBreak())
        flowables.extend(_build_result_flowables(result, school_config, ca_max, exam_max))

    doc.build(flowables)
    buffer.seek(0)
    return buffer


def build_student_credentials_pdf(students, decrypt_password_fn):
    """
    students: list of Student rows (any scope the caller chooses — one
    class arm, or the whole school).
    decrypt_password_fn: pass app.services.security.decrypt_password —
    kept as a parameter rather than imported directly so this module
    doesn't need to know about security.py, matching how the rest of
    this file only depends on app.models + app.services.results.

    One row per student: name, admission number, class, and their
    plaintext password (recovered from password_encrypted). Intended for
    printing and handing to parents at resumption/registration — NOT for
    routine distribution or emailing in bulk, since it's a plaintext
    password dump. Treat the generated PDF itself as sensitive: don't
    leave printed copies lying around, and delete the file after
    distributing.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )

    school_config = SchoolConfig.query.first()
    school_name = school_config.school_name if school_config else "School"

    flowables = [
        Paragraph(school_name, _school_name_style),
        Paragraph("Student Portal Login Credentials", _doc_title_style),
        Paragraph("Confidential — for distribution to parents/guardians only.", _term_line_style),
        Spacer(1, 6),
    ]

    header = ["Student Name", "Admission No.", "Class", "Password"]
    rows = [header]
    sorted_students = sorted(
        students,
        key=lambda s: (s.class_arm.display_name if s.class_arm else "", s.full_name),
    )
    for student in sorted_students:
        password = decrypt_password_fn(student.password_encrypted) or "(reset required)"
        rows.append([
            student.full_name,
            student.admission_number,
            student.class_arm.display_name if student.class_arm else "—",
            password,
        ])

    table = Table(rows, colWidths=[55 * mm, 35 * mm, 35 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flowables.append(table)

    doc.build(flowables)
    buffer.seek(0)
    return buffer
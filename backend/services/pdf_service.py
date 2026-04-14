import uuid
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _clean_text(value: str | None, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _to_paragraph_markup(value: str | None, fallback: str = "-") -> str:
    text = _clean_text(value, fallback)
    return escape(text).replace("\n", "<br/>")


def _paragraph_style_for_text(value: str | None, styles: dict[str, ParagraphStyle], small: bool = False):
    text = _clean_text(value, "")
    has_non_ascii = any(ord(ch) > 127 for ch in text)
    if small:
        return styles["small_tamil"] if has_non_ascii else styles["small"]
    return styles["tamil"] if has_non_ascii else styles["body"]


def _register_fonts() -> tuple[str, str]:
    latin_font = "Helvetica"
    tamil_font = "Helvetica"
    font_path = Path(current_app.config["FONT_PATH"])
    if font_path.exists():
        tamil_name = "NotoSansTamil"
        if tamil_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(tamil_name, str(font_path)))
        tamil_font = tamil_name
    return latin_font, tamil_font


def _build_styles(latin_font: str, tamil_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "eta-title",
            parent=base["Heading1"],
            fontName=f"{latin_font}-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0B2B56"),
            spaceAfter=2 * mm,
        ),
        "meta": ParagraphStyle(
            "eta-meta",
            parent=base["Normal"],
            fontName=latin_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
        ),
        "section": ParagraphStyle(
            "eta-section",
            parent=base["Heading3"],
            fontName=f"{latin_font}-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "eta-body",
            parent=base["Normal"],
            fontName=latin_font,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#111827"),
        ),
        "tamil": ParagraphStyle(
            "eta-tamil",
            parent=base["Normal"],
            fontName=tamil_font,
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#111827"),
        ),
        "small": ParagraphStyle(
            "eta-small",
            parent=base["Normal"],
            fontName=latin_font,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
        ),
        "small_tamil": ParagraphStyle(
            "eta-small-tamil",
            parent=base["Normal"],
            fontName=tamil_font,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#4B5563"),
        ),
    }


def _draw_footer(canvas_obj, doc_obj):
    canvas_obj.saveState()
    footer_y = 10 * mm
    canvas_obj.setStrokeColor(colors.HexColor("#D1D5DB"))
    canvas_obj.line(doc_obj.leftMargin, footer_y + 4 * mm, A4[0] - doc_obj.rightMargin, footer_y + 4 * mm)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#6B7280"))
    canvas_obj.drawString(doc_obj.leftMargin, footer_y, "AI-assisted screening only. Final clinical decision must be made by a qualified doctor.")
    canvas_obj.drawRightString(A4[0] - doc_obj.rightMargin, footer_y, f"Page {canvas_obj.getPageNumber()}")
    canvas_obj.restoreState()


def _kv_table(styles: dict[str, ParagraphStyle], report: dict) -> Table:
    patient_name = _clean_text(report.get("patient_name"), "Not Provided")
    diagnosis = _clean_text(report.get("diagnosis"), "Pending")
    severity = _clean_text(report.get("severity"), "unknown")
    ai_source_text = "Live AI" if report.get("ai_source") == "real" else "Fallback/Mock"
    
    rows = [
        [Paragraph("<b>Patient Name</b>", styles["body"]), Paragraph(_to_paragraph_markup(patient_name), _paragraph_style_for_text(patient_name, styles))],
        [Paragraph("<b>Scan ID</b>", styles["body"]), Paragraph(str(report.get("scan_id", "-")), styles["body"])],
        [Paragraph("<b>Generated At</b>", styles["body"]), Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["body"])],
        [Paragraph("<b>Diagnosis</b>", styles["body"]), Paragraph(_to_paragraph_markup(diagnosis), _paragraph_style_for_text(diagnosis, styles))],
        [Paragraph("<b>Severity</b>", styles["body"]), Paragraph(_to_paragraph_markup(severity), _paragraph_style_for_text(severity, styles))],
        [Paragraph("<b>Confidence</b>", styles["body"]), Paragraph(f"{int(report.get('confidence_pct', 0) or 0)}%", styles["body"])],
        [Paragraph("<b>AI Source</b>", styles["body"]), Paragraph(ai_source_text, styles["body"])],
    ]
    table = Table(rows, colWidths=[40 * mm, 140 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#EFF6FF")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _scan_image_block(scan_image_path: str | Path) -> Image | None:
    image_path = Path(scan_image_path)
    if not image_path.exists():
        return None
    try:
        reader = ImageReader(str(image_path))
        img_w, img_h = reader.getSize()
        if img_w <= 0 or img_h <= 0:
            return None
        max_w = 150 * mm
        max_h = 90 * mm
        scale = min(max_w / img_w, max_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        image = Image(str(image_path), width=draw_w, height=draw_h)
        image.hAlign = "LEFT"
        return image
    except Exception:
        return None


def generate_report_pdf(report: dict, scan_image_path: str | Path) -> Path:
    report_dir = Path(current_app.config["REPORT_DIR"])
    report_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = report_dir / f"eta_report_{uuid.uuid4().hex}.pdf"

    try:
        latin_font, tamil_font = _register_fonts()
        styles = _build_styles(latin_font, tamil_font)
        summary = report.get("summary_json") or {}

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=20 * mm,
            title="ETA Trauma Report",
            author="Emergency Trauma Analyzer",
        )

        story = []
        story.append(Paragraph("Emergency Trauma Analyzer (ETA)", styles["title"]))
        story.append(Paragraph("Trauma Screening Report", styles["meta"]))
        story.append(Spacer(1, 2 * mm))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#BFDBFE"), thickness=1.2))
        story.append(Spacer(1, 4 * mm))

        story.append(_kv_table(styles, report))
        story.append(Spacer(1, 5 * mm))

        story.append(Paragraph("Uploaded Scan", styles["section"]))
        image = _scan_image_block(scan_image_path)
        if image is not None:
            story.append(image)
        else:
            story.append(Paragraph("Scan image unavailable in storage.", styles["body"]))
        story.append(Spacer(1, 5 * mm))

        doctor_review = _clean_text(summary.get("doctor_review_text"), "No doctor review entered.")
        patient_summary = _clean_text(summary.get("patient_summary_text"), "No patient summary entered.")
        ai_summary = _clean_text(summary.get("ai_summary_text"), "No AI summary available.")

        story.append(Paragraph("Doctor Review", styles["section"]))
        story.append(Paragraph(_to_paragraph_markup(doctor_review), _paragraph_style_for_text(doctor_review, styles)))
        story.append(Spacer(1, 3 * mm))

        story.append(Paragraph("Patient Summary", styles["section"]))
        story.append(Paragraph(_to_paragraph_markup(patient_summary), _paragraph_style_for_text(patient_summary, styles)))
        story.append(Spacer(1, 3 * mm))

        story.append(Paragraph("AI Summary (Reference)", styles["section"]))
        story.append(Paragraph(_to_paragraph_markup(ai_summary), _paragraph_style_for_text(ai_summary, styles)))
        story.append(Spacer(1, 4 * mm))

        missing_field_values = report.get("missing_field_values") or {}
        if not isinstance(missing_field_values, dict):
            missing_field_values = {}
        missing_fields = report.get("missing_fields") or []

        story.append(Paragraph("Required Clinical Inputs", styles["section"]))
        if missing_field_values:
            rows = [[Paragraph("<b>Field</b>", styles["body"]), Paragraph("<b>Value</b>", styles["body"])]]
            for key in sorted(missing_field_values.keys()):
                value = _clean_text(missing_field_values.get(key), "-")
                rows.append([Paragraph(key, styles["body"]), Paragraph(value, styles["body"])])
            table = Table(rows, colWidths=[58 * mm, 122 * mm], hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)
        else:
            story.append(Paragraph("No additional clinical inputs were captured.", styles["body"]))

        if missing_fields:
            story.append(Spacer(1, 2 * mm))
            unresolved = ", ".join(sorted(missing_fields))
            story.append(Paragraph(f"Still missing: {unresolved}", styles["small"]))
        story.append(Spacer(1, 4 * mm))

        disclaimer_en = _clean_text(
            summary.get(
                "safety_disclaimer_en",
                "AI-assisted screening only. Final clinical decision must be made by a qualified doctor.",
            )
        )
        story.append(Paragraph("Safety Disclaimer", styles["section"]))
        story.append(Paragraph(_to_paragraph_markup(disclaimer_en), _paragraph_style_for_text(disclaimer_en, styles, small=True)))

        doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
        return pdf_path
    except Exception as e:
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
        raise RuntimeError(f"Failed to generate PDF: {str(e)}")

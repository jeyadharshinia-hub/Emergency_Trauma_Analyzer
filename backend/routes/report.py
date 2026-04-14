import re
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from auth_utils import get_current_user, login_required
from extensions import db
from models.patient import Patient
from models.report import Report
from models.scan_patient_link import ScanPatientLink
from models.scan import Scan
from services.pdf_service import generate_report_pdf


report_bp = Blueprint("report", __name__, url_prefix="/api/reports")


def _public_static_url(path_value: str) -> str:
    normalized = path_value.replace("\\", "/")
    idx = normalized.find("static/")
    if idx >= 0:
        return "/" + normalized[idx:]
    return "/static/uploads/" + Path(normalized).name


def _patient_payload(scan: Scan) -> dict | None:
    link = scan.patient_link
    if not link or not link.patient:
        return None
    patient = link.patient
    return {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone or "",
    }


def _coerce_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _compose_ai_summary_from_structured(report: Report) -> str:
    ai_json = report.ai_json or {}
    findings = ai_json.get("primary_findings") or []
    findings_text = ", ".join([_coerce_text(item) for item in findings if _coerce_text(item)])
    condition = _coerce_text(ai_json.get("suspected_condition")) or "other"
    body_region = _coerce_text(ai_json.get("body_region")) or "unknown region"
    diagnosis = _coerce_text(report.diagnosis) or "pending medical review"
    severity = _coerce_text(report.severity) or "unknown"
    confidence_pct = int(report.confidence_pct or 0)
    parts = [
        f"AI screening suggests {diagnosis.lower()} in the {body_region}.",
        f"Suspected condition tag: {condition}.",
        f"Severity: {severity}.",
        f"Confidence: {confidence_pct}%.",
    ]
    if findings_text:
        parts.append(f"Key findings: {findings_text}.")
    return " ".join(parts)


def _resolve_ai_summary_text(report: Report, summary: dict) -> str:
    candidates = [
        summary.get("ai_summary_text"),
        summary.get("doctor_summary_en"),
    ]
    for candidate in candidates:
        value = _coerce_text(candidate)
        if value:
            return value
    return _compose_ai_summary_from_structured(report)


def _resolve_doctor_review_text(report: Report, final: dict, summary: dict) -> str:
    if "doctor_review_text" in final:
        return _coerce_text(final.get("doctor_review_text"))

    candidates = [
        report.doctor_notes,
        final.get("doctor_summary_en"),
        final.get("doctor_summary_ta"),
        summary.get("doctor_summary_en"),
        summary.get("doctor_summary_ta"),
    ]
    for candidate in candidates:
        value = _coerce_text(candidate)
        if value:
            return value
    return ""


def _resolve_patient_summary_text(final: dict, summary: dict) -> str:
    if "patient_summary_text" in final:
        return _coerce_text(final.get("patient_summary_text"))

    candidates = [
        final.get("patient_summary_en"),
        final.get("patient_summary_ta"),
        summary.get("patient_summary_en"),
        summary.get("patient_summary_ta"),
    ]
    for candidate in candidates:
        value = _coerce_text(candidate)
        if value:
            return value
    return ""


def _editable_payload(report: Report) -> dict:
    summary = report.summary_json or {}
    final = report.final_json or {}
    ai_summary_text = _resolve_ai_summary_text(report, summary)
    doctor_review_text = _resolve_doctor_review_text(report, final, summary)
    patient_summary_text = _resolve_patient_summary_text(final, summary)

    legacy_doctor_summary_en = _coerce_text(final.get("doctor_summary_en")) or _coerce_text(
        summary.get("doctor_summary_en")
    )
    legacy_doctor_summary_ta = _coerce_text(final.get("doctor_summary_ta")) or _coerce_text(
        summary.get("doctor_summary_ta")
    )
    legacy_patient_summary_en = _coerce_text(final.get("patient_summary_en")) or _coerce_text(
        summary.get("patient_summary_en")
    )
    legacy_patient_summary_ta = _coerce_text(final.get("patient_summary_ta")) or _coerce_text(
        summary.get("patient_summary_ta")
    )

    missing_field_values = final.get("missing_field_values")
    if not isinstance(missing_field_values, dict):
        missing_field_values = {}
    return {
        "scan_id": report.scan_id,
        "patient_name": report.patient_name or "",
        "diagnosis": report.diagnosis or "",
        "severity": report.severity,
        "confidence_pct": report.confidence_pct,
        "doctor_notes": report.doctor_notes or doctor_review_text,
        "ai_summary_text": ai_summary_text,
        "doctor_review_text": doctor_review_text,
        "patient_summary_text": patient_summary_text,
        "missing_fields": report.missing_fields or [],
        "doctor_summary_en": legacy_doctor_summary_en,
        "doctor_summary_ta": legacy_doctor_summary_ta,
        "patient_summary_en": legacy_patient_summary_en,
        "patient_summary_ta": legacy_patient_summary_ta,
        "missing_field_values": missing_field_values,
        "safety_disclaimer_en": summary.get(
            "safety_disclaimer_en",
            "AI-assisted screening only. Final clinical decision must be made by a qualified doctor.",
        ),
        "safety_disclaimer_ta": summary.get("safety_disclaimer_ta", ""),
        "ai_source": report.ai_source,
        "ai_warning": report.ai_warning,
    }


def _can_access_scan(user, scan: Scan | None) -> bool:
    if not user or not scan:
        return False
    return scan.user_id == user.id


def _parse_pagination() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", "20"))
    except ValueError:
        page_size = 20
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    return page, page_size


def _parse_patient_id(raw_value: str | None) -> tuple[int | None, str | None]:
    if raw_value is None:
        return None, None
    value = str(raw_value).strip()
    if not value:
        return None, None
    try:
        patient_id = int(value)
    except ValueError:
        return None, "patient_id must be an integer."
    if patient_id <= 0:
        return None, "patient_id must be a positive integer."
    return patient_id, None


def _report_history_item(scan: Scan) -> dict:
    report = scan.report
    patient = scan.patient_link.patient if scan.patient_link and scan.patient_link.patient else None
    return {
        "scan_id": scan.id,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "scan_type": scan.scan_type,
        "analyze_status": scan.analyze_status,
        "patient": {
            "id": patient.id,
            "patient_code": patient.patient_code,
            "full_name": patient.full_name,
        }
        if patient
        else None,
        "report": {
            "diagnosis": report.diagnosis or "",
            "severity": report.severity,
            "confidence_pct": report.confidence_pct,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
            "has_pdf_download": True,
        }
        if report
        else None,
        "has_report": bool(report),
    }


@report_bp.get("/history")
@login_required
def get_report_history():
    user = get_current_user()
    page, page_size = _parse_pagination()
    query_text = (request.args.get("query") or "").strip()
    status = (request.args.get("status") or "all").strip().lower()
    patient_id, patient_id_error = _parse_patient_id(request.args.get("patient_id"))
    if patient_id_error:
        return jsonify({"error": patient_id_error}), 400

    allowed_statuses = {"all", "with_report", "no_report"}
    if status not in allowed_statuses:
        return jsonify({"error": "status must be all|with_report|no_report"}), 400

    if patient_id is not None:
        target_patient = Patient.query.filter_by(id=patient_id, owner_user_id=user.id).first()
        if not target_patient:
            return jsonify({"error": "Patient not found."}), 404

    base = Scan.query.filter(Scan.user_id == user.id)
    needs_patient_join = bool(query_text) or patient_id is not None
    needs_report_join = status != "all" or bool(query_text)
    if needs_patient_join:
        base = base.outerjoin(ScanPatientLink, ScanPatientLink.scan_id == Scan.id).outerjoin(
            Patient, Patient.id == ScanPatientLink.patient_id
        )
    if needs_report_join:
        base = base.outerjoin(Report, Report.scan_id == Scan.id)

    if patient_id is not None:
        base = base.filter(ScanPatientLink.patient_id == patient_id)

    if query_text:
        like = f"%{query_text}%"
        base = base.filter(
            or_(
                Patient.full_name.ilike(like),
                Patient.patient_code.ilike(like),
                Report.diagnosis.ilike(like),
            )
        )

    if status == "with_report":
        base = base.filter(Report.id.isnot(None))
    elif status == "no_report":
        base = base.filter(Report.id.is_(None))

    total = base.count()
    scans = (
        base.options(
            joinedload(Scan.report),
            joinedload(Scan.patient_link).joinedload(ScanPatientLink.patient),
        )
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify(
        {
            "items": [_report_history_item(scan) for scan in scans],
            "total": total,
            "page": page,
            "page_size": page_size,
            "status": status,
            "query": query_text,
            "patient_id": patient_id,
        }
    )


@report_bp.get("/<int:scan_id>")
@login_required
def get_report(scan_id: int):
    user = get_current_user()
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        return jsonify({"error": "Scan not found"}), 404

    report = Report.query.filter_by(scan_id=scan.id).first()
    if not report:
        return jsonify({"error": "Report not found. Run analysis first."}), 404

    return jsonify(
        {
            "scan": {
                "id": scan.id,
                "scan_type": scan.scan_type,
                "image_url": _public_static_url(scan.original_image_path),
                "processed_image_url": _public_static_url(scan.processed_image_path),
            },
            "patient": _patient_payload(scan),
            "report": _editable_payload(report),
        }
    )


@report_bp.put("/<int:scan_id>")
@login_required
def update_report(scan_id: int):
    user = get_current_user()
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        return jsonify({"error": "Scan not found"}), 404
    report = Report.query.filter_by(scan_id=scan.id).first()
    if not report:
        return jsonify({"error": "Report not found"}), 404

    payload = request.get_json(silent=True) or {}
    report.patient_name = payload.get("patient_name", report.patient_name)
    report.diagnosis = payload.get("diagnosis", report.diagnosis)
    report.severity = payload.get("severity", report.severity)
    report.missing_fields = payload.get("missing_fields", report.missing_fields or [])

    final_json = dict(report.final_json or {})

    incoming_doctor_review = payload.get("doctor_review_text")
    if incoming_doctor_review is None:
        incoming_doctor_review = payload.get("doctor_summary_en")
    if incoming_doctor_review is None:
        incoming_doctor_review = payload.get("doctor_summary_ta")
    if incoming_doctor_review is not None:
        doctor_review_text = _coerce_text(incoming_doctor_review)
        final_json["doctor_review_text"] = doctor_review_text
        report.doctor_notes = doctor_review_text
    else:
        report.doctor_notes = payload.get("doctor_notes", report.doctor_notes)

    incoming_patient_summary = payload.get("patient_summary_text")
    if incoming_patient_summary is None:
        incoming_patient_summary = payload.get("patient_summary_en")
    if incoming_patient_summary is None:
        incoming_patient_summary = payload.get("patient_summary_ta")
    if incoming_patient_summary is not None:
        final_json["patient_summary_text"] = _coerce_text(incoming_patient_summary)

    raw_missing_values = payload.get("missing_field_values", final_json.get("missing_field_values", {}))
    if not isinstance(raw_missing_values, dict):
        raw_missing_values = {}
    normalized_missing_values = {}
    for key, value in raw_missing_values.items():
        name = str(key).strip()
        if not name:
            continue
        normalized_missing_values[name] = str(value).strip() if value is not None else ""
    final_json["missing_field_values"] = normalized_missing_values

    tracked_fields = set(report.missing_fields or [])
    tracked_fields.update(normalized_missing_values.keys())
    unresolved = [name for name in tracked_fields if not normalized_missing_values.get(name, "").strip()]
    report.missing_fields = sorted(unresolved)

    report.final_json = final_json

    db.session.commit()
    return jsonify({"report": _editable_payload(report)})


@report_bp.get("/<int:scan_id>/pdf")
@login_required
def download_pdf(scan_id: int):
    print(f"[DEBUG] PDF download requested for scan_id={scan_id}")
    user = get_current_user()
    print(f"[DEBUG] Current user: {user}")
    
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        print(f"[DEBUG] Access denied or scan not found for scan_id={scan_id}")
        return jsonify({"error": "Scan not found"}), 404
    
    report = Report.query.filter_by(scan_id=scan.id).first()
    if not report:
        print(f"[DEBUG] Report not found for scan_id={scan_id}")
        return jsonify({"error": "Report not found"}), 404

    try:
        print(f"[DEBUG] Generating PDF for scan_id={scan_id}")
        # Validate scan has processed image
        if not scan.processed_image_path:
            print(f"[DEBUG] Processed image path not set")
            return jsonify({"error": "Scan image path is not set"}), 400
        
        merged_report = _editable_payload(report)
        
        # Ensure all fields have proper defaults and are safe for PDF generation
        merged_report["patient_name"] = _coerce_text(merged_report.get("patient_name")) or "Not Provided"
        merged_report["diagnosis"] = _coerce_text(merged_report.get("diagnosis")) or "Pending"
        merged_report["severity"] = _coerce_text(merged_report.get("severity")) or "unknown"
        merged_report["confidence_pct"] = merged_report.get("confidence_pct") or 0
        merged_report["scan_id"] = merged_report.get("scan_id") or scan_id
        merged_report["ai_source"] = merged_report.get("ai_source") or "mock"
        merged_report["ai_warning"] = _coerce_text(merged_report.get("ai_warning")) or ""
        
        # Build summary_json with all required fields
        merged_report["summary_json"] = {
            "ai_summary_text": _coerce_text(merged_report.get("ai_summary_text", "")),
            "doctor_review_text": _coerce_text(merged_report.get("doctor_review_text", "")),
            "patient_summary_text": _coerce_text(merged_report.get("patient_summary_text", "")),
            "safety_disclaimer_en": _coerce_text(
                merged_report.get("safety_disclaimer_en", 
                "AI-assisted screening only. Final clinical decision must be made by a qualified doctor.")
            ),
            "safety_disclaimer_ta": _coerce_text(merged_report.get("safety_disclaimer_ta", "")),
        }
        
        print(f"[DEBUG] Calling generate_report_pdf...")
        pdf_path = generate_report_pdf(merged_report, scan.processed_image_path)
        print(f"[DEBUG] PDF generated at {pdf_path}")
        
        report.pdf_path = str(pdf_path)
        db.session.commit()

        patient = scan.patient_link.patient if scan.patient_link and scan.patient_link.patient else None
        raw_name = (patient.full_name if patient else None) or report.patient_name or f"scan_{scan.id}"
        safe_name = re.sub(r"[^\w\-]", "_", raw_name).strip("_") or f"scan_{scan.id}"
        date_str = (report.updated_at or report.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        download_name = f"eta_report_{safe_name}_{date_str}.pdf"

        print(f"[DEBUG] Sending file: {download_name}")
        print(f"[DEBUG] PDF file exists: {Path(pdf_path).exists()}")
        print(f"[DEBUG] PDF file size: {Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 'N/A'}")
        
        response = send_file(
            str(pdf_path),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=download_name,
        )
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except FileNotFoundError as e:
        print(f"[DEBUG] FileNotFoundError: {str(e)}")
        return jsonify({"error": f"Scan image not found. Please ensure the image file exists."}), 400
    except RuntimeError as e:
        print(f"[DEBUG] RuntimeError: {str(e)}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"[DEBUG] Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate PDF report: {str(e)}"}), 500

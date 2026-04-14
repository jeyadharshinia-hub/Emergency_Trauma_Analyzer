import re
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from auth_utils import require_role
from extensions import bcrypt, db
from models.patient import Patient
from models.report import Report
from models.scan import Scan
from models.scan_patient_link import ScanPatientLink
from models.user import User
from services.pdf_service import generate_report_pdf


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


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


@admin_bp.get("/stats")
@require_role("admin")
def get_stats():
    total_doctors = User.query.filter_by(role="doctor").count()
    total_patients = Patient.query.filter_by(is_active=True).count()
    total_scans = Scan.query.count()
    total_reports = Report.query.count()
    return jsonify(
        {
            "total_doctors": total_doctors,
            "total_patients": total_patients,
            "total_scans": total_scans,
            "total_reports": total_reports,
        }
    )


@admin_bp.get("/users")
@require_role("admin")
def list_users():
    users = User.query.filter_by(role="doctor").order_by(User.created_at.desc()).all()
    return jsonify(
        {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
        }
    )


@admin_bp.post("/users")
@require_role("admin")
def create_user():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(username=username, password_hash=hashed, role="doctor")
    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                }
            }
        ),
        201,
    )


@admin_bp.delete("/users/<int:user_id>")
@require_role("admin")
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user or user.role == "admin":
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.get("/reports")
@require_role("admin")
def list_all_reports():
    page, page_size = _parse_pagination()

    query_text = (request.args.get("query") or "").strip()

    base = (
        Scan.query.join(Report, Report.scan_id == Scan.id)
        .outerjoin(ScanPatientLink, ScanPatientLink.scan_id == Scan.id)
        .outerjoin(Patient, Patient.id == ScanPatientLink.patient_id)
        .join(User, User.id == Scan.user_id)
    )

    if query_text:
        like = f"%{query_text}%"
        base = base.filter(
            or_(
                Patient.full_name.ilike(like),
                Patient.patient_code.ilike(like),
                Report.diagnosis.ilike(like),
                User.username.ilike(like),
            )
        )

    total = base.count()
    scans = (
        base.options(
            joinedload(Scan.report),
            joinedload(Scan.patient_link).joinedload(ScanPatientLink.patient),
            joinedload(Scan.user),
        )
        .order_by(Scan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for scan in scans:
        report = scan.report
        patient = (
            scan.patient_link.patient
            if scan.patient_link and scan.patient_link.patient
            else None
        )
        items.append(
            {
                "scan_id": scan.id,
                "doctor": scan.user.username if scan.user else "unknown",
                "scan_type": scan.scan_type,
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
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
                }
                if report
                else None,
            }
        )

    return jsonify({"items": items, "total": total, "page": page, "page_size": page_size})


@admin_bp.get("/patients")
@require_role("admin")
def list_patients():
    page, page_size = _parse_pagination()
    query_text = (request.args.get("query") or "").strip()
    owner_join = User.id == Patient.owner_user_id

    filters = []
    if query_text:
        like = f"%{query_text}%"
        filters.append(
            or_(
                Patient.full_name.ilike(like),
                Patient.patient_code.ilike(like),
                Patient.phone.ilike(like),
                User.username.ilike(like),
            )
        )

    base_count = Patient.query.filter(Patient.is_active.is_(True)).outerjoin(
        User, owner_join
    )
    if filters:
        base_count = base_count.filter(*filters)
    total = base_count.count()

    patients_query = (
        db.session.query(
            Patient,
            User.username.label("owner_username"),
            func.count(ScanPatientLink.scan_id).label("scan_count"),
            func.max(Scan.created_at).label("last_scan_at"),
        )
        .filter(Patient.is_active.is_(True))
        .outerjoin(User, owner_join)
        .outerjoin(ScanPatientLink, ScanPatientLink.patient_id == Patient.id)
        .outerjoin(Scan, ScanPatientLink.scan_id == Scan.id)
        .group_by(Patient.id, User.username)
    )
    if filters:
        patients_query = patients_query.filter(*filters)
    patients = (
        patients_query.order_by(Patient.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for patient, owner_username, scan_count, last_scan_at in patients:
        items.append(
            {
                "id": patient.id,
                "patient_code": patient.patient_code,
                "full_name": patient.full_name,
                "age": patient.age,
                "gender": patient.gender,
                "phone": patient.phone or "",
                "notes": patient.notes or "",
                "owner_username": owner_username or "-",
                "scan_count": int(scan_count or 0),
                "last_scan_at": last_scan_at.isoformat() if last_scan_at else None,
                "is_active": bool(patient.is_active),
                "created_at": patient.created_at.isoformat() if patient.created_at else None,
            }
        )

    return jsonify(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


@admin_bp.get("/activity")
@require_role("admin")
def get_activity():
    try:
        limit = int(request.args.get("limit", "10"))
    except ValueError:
        limit = 10
    limit = max(5, min(50, limit))

    scans = (
        Scan.query.options(
            joinedload(Scan.user),
            joinedload(Scan.patient_link).joinedload(ScanPatientLink.patient),
            joinedload(Scan.report),
        )
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for scan in scans:
        patient = (
            scan.patient_link.patient
            if scan.patient_link and scan.patient_link.patient
            else None
        )
        report = scan.report
        items.append(
            {
                "scan_id": scan.id,
                "scan_type": scan.scan_type,
                "status": scan.analyze_status,
                "created_at": scan.created_at.isoformat()
                if scan.created_at
                else None,
                "doctor": scan.user.username if scan.user else "-",
                "patient": {
                    "id": patient.id,
                    "patient_code": patient.patient_code,
                    "full_name": patient.full_name,
                }
                if patient
                else None,
                "report": {
                    "diagnosis": report.diagnosis,
                    "severity": report.severity,
                    "confidence_pct": report.confidence_pct,
                    "updated_at": report.updated_at.isoformat()
                    if report and report.updated_at
                    else None,
                }
                if report
                else None,
                "has_report": bool(report),
            }
        )

    return jsonify({"items": items})


@admin_bp.get("/reports/<int:scan_id>/pdf")
@require_role("admin")
def admin_download_pdf(scan_id: int):
    from routes.report import _editable_payload

    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    report = Report.query.filter_by(scan_id=scan.id).first()
    if not report:
        return jsonify({"error": "Report not found"}), 404

    merged_report = _editable_payload(report)
    merged_report["summary_json"] = {
        "ai_summary_text": merged_report.get("ai_summary_text", ""),
        "doctor_review_text": merged_report.get("doctor_review_text", ""),
        "patient_summary_text": merged_report.get("patient_summary_text", ""),
        "safety_disclaimer_en": merged_report["safety_disclaimer_en"],
        "safety_disclaimer_ta": merged_report["safety_disclaimer_ta"],
    }
    pdf_path = generate_report_pdf(merged_report, scan.processed_image_path)
    report.pdf_path = str(pdf_path)
    db.session.commit()

    patient = (
        scan.patient_link.patient
        if scan.patient_link and scan.patient_link.patient
        else None
    )
    raw_name = (patient.full_name if patient else None) or report.patient_name or f"scan_{scan.id}"
    safe_name = re.sub(r"[^\w\-]", "_", raw_name).strip("_") or f"scan_{scan.id}"
    date_str = (report.updated_at or report.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
    download_name = f"eta_report_{safe_name}_{date_str}.pdf"

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


@admin_bp.get("/archived-patients")
@require_role("admin")
def list_archived_patients():
    """List all archived (soft-deleted) patient records."""
    page, page_size = _parse_pagination()
    query_text = (request.args.get("query") or "").strip()

    owner_join = User.id == Patient.owner_user_id
    base = Patient.query.filter_by(is_active=False).outerjoin(User, owner_join)

    if query_text:
        like = f"%{query_text}%"
        base = base.filter(
            or_(
                Patient.patient_code.ilike(like),
                Patient.full_name.ilike(like),
                Patient.phone.ilike(like),
                User.username.ilike(like),
            )
        )

    total = base.count()
    archived_patients = (
        db.session.query(
            Patient,
            User.username.label("owner_username"),
            func.count(ScanPatientLink.scan_id).label("scan_count"),
        )
        .filter(Patient.is_active == False)
        .outerjoin(User, owner_join)
        .outerjoin(ScanPatientLink, ScanPatientLink.patient_id == Patient.id)
        .group_by(Patient.id, User.username)
    )

    if query_text:
        like = f"%{query_text}%"
        archived_patients = archived_patients.filter(
            or_(
                Patient.patient_code.ilike(like),
                Patient.full_name.ilike(like),
                Patient.phone.ilike(like),
                User.username.ilike(like),
            )
        )

    archived_patients = (
        archived_patients.order_by(Patient.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for patient, owner_username, scan_count in archived_patients:
        items.append(
            {
                "id": patient.id,
                "patient_code": patient.patient_code,
                "full_name": patient.full_name,
                "age": patient.age,
                "gender": patient.gender,
                "phone": patient.phone or "",
                "owner_username": owner_username or "-",
                "scan_count": int(scan_count or 0),
                "created_at": patient.created_at.isoformat() if patient.created_at else None,
                "archived_date": patient.updated_at.isoformat() if patient.updated_at else None,
            }
        )

    return jsonify(
        {"items": items, "total": total, "page": page, "page_size": page_size}
    )


@admin_bp.post("/archived-patients/<int:patient_id>/restore")
@require_role("admin")
def restore_archived_patient(patient_id: int):
    """Restore an archived patient (set is_active back to True)."""
    patient = Patient.query.filter_by(id=patient_id, is_active=False).first()
    if not patient:
        return jsonify({"error": "Archived patient not found"}), 404

    patient.is_active = True
    db.session.commit()

    return jsonify(
        {
            "message": "Patient restored successfully",
            "patient": {
                "id": patient.id,
                "patient_code": patient.patient_code,
                "full_name": patient.full_name,
            },
        }
    )

import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from auth_utils import (
    get_current_user,
    login_required,
)
from extensions import db
from models.patient import Patient
from models.report import Report
from models.scan import Scan
from models.scan_patient_link import ScanPatientLink
from services.errors import AIContractError, AIServiceUnavailableError, NonMedicalImageError
from services.gemini_service import analyze_scan
from services.groq_service import generate_summary
from services.image_service import preprocess_image


scan_bp = Blueprint("scan", __name__, url_prefix="/api/scans")

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
VALID_SCAN_TYPES = {"xray", "ct", "mri"}
MOCK_MARKERS = (
    "mock mode",
    "mock summary",
    "demo summary",
    "demo report only",
    "use_mock_ai",
    "ui/demo",
    "non-diagnostic output is for ui/demo",
)


def _public_static_url(path_value: str) -> str:
    normalized = path_value.replace("\\", "/")
    idx = normalized.find("static/")
    if idx >= 0:
        return "/" + normalized[idx:]
    return "/static/uploads/" + Path(normalized).name


def _diagnosis_from_condition(condition: str) -> str:
    mapping = {
        "bone_fracture": "Possible Bone Fracture",
        "brain_hemorrhage": "Possible Brain Hemorrhage",
        "pneumothorax": "Possible Pneumothorax",
        "no_clear_finding": "No Clear Finding",
        "other": "Other Trauma Indicator",
    }
    return mapping.get(condition, "Pending Medical Review")


def _coerce_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _compose_ai_summary_text(
    summary_json: dict,
    gemini_json: dict,
    diagnosis: str,
    severity: str,
    confidence_pct: int,
) -> str:
    existing = _coerce_text(summary_json.get("ai_summary_text"))
    if existing:
        return existing

    legacy = _coerce_text(summary_json.get("doctor_summary_en"))
    if legacy:
        return legacy

    findings = gemini_json.get("primary_findings") or []
    findings_text = ", ".join([_coerce_text(item) for item in findings if _coerce_text(item)])
    body_region = _coerce_text(gemini_json.get("body_region")) or "unknown region"
    condition = _coerce_text(gemini_json.get("suspected_condition")) or "other"

    parts = [
        f"AI screening suggests {diagnosis.lower()} in the {body_region}.",
        f"Suspected condition tag: {condition}.",
        f"Severity: {severity}.",
        f"Confidence: {confidence_pct}%.",
    ]
    if findings_text:
        parts.append(f"Key findings: {findings_text}.")
    return " ".join(parts)


def _patient_payload(patient: Patient | None) -> dict | None:
    if not patient:
        return None
    return {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone or "",
    }


def _safe_fallback_scan(scan_type: str, reason: str) -> dict:
    return {
        "scan_type": scan_type,
        "body_region": "unknown",
        "primary_findings": [
            "Live AI services were unavailable during analysis.",
        ],
        "suspected_condition": "no_clear_finding",
        "severity": "unknown",
        "confidence_pct": 12,
        "notes_for_doctor": (
            "Generated safe fallback output. Re-run analysis later and rely on clinical judgment."
        ),
        "limitations": f"AI unavailable: {reason}",
        "is_medical_scan": True,
        "rejection_reason": "",
    }


def _safe_fallback_summary() -> dict:
    ai_summary_text = "Live AI service was unavailable. No diagnostic inference was produced."
    return {
        "ai_summary_text": ai_summary_text,
        "doctor_summary_en": ai_summary_text,
        "doctor_summary_ta": (
            "Live AI சேவை கிடைக்கவில்லை. நோயறிதல் முடிவு உருவாக்கப்படவில்லை."
        ),
        "patient_summary_en": (
            "Automated analysis is temporarily unavailable. Doctor review is required."
        ),
        "patient_summary_ta": (
            "தானியங்கி பகுப்பாய்வு தற்காலிகமாக இல்லை. மருத்துவர் மதிப்பீடு அவசியம்."
        ),
        "missing_fields": ["Age", "Gender", "Injury mechanism", "Symptoms", "Vitals"],
        "safety_disclaimer_en": (
            "AI-assisted screening only. Final clinical decision must be made by a qualified doctor."
        ),
        "safety_disclaimer_ta": (
            "இது AI உதவியுள்ள ஆரம்ப பரிசோதனை மட்டும். இறுதி மருத்துவ முடிவை தகுதியான மருத்துவர் மட்டுமே எடுக்க வேண்டும்."
        ),
    }


def _contains_mock_marker(value) -> bool:
    text = _coerce_text(value).lower()
    if not text:
        return False
    return any(marker in text for marker in MOCK_MARKERS)


def _summary_has_mock_markers(summary_json: dict) -> bool:
    if not isinstance(summary_json, dict):
        return False
    for value in summary_json.values():
        if isinstance(value, list):
            if any(_contains_mock_marker(item) for item in value):
                return True
            continue
        if _contains_mock_marker(value):
            return True
    return False


def _ai_unavailable_code(message: str) -> str:
    normalized = (message or "").lower()
    if "quota" in normalized or "rate limit" in normalized:
        return "AI_QUOTA_EXCEEDED"
    if "authentication failed" in normalized or "api key" in normalized:
        return "AI_AUTH_INVALID"
    return "AI_UNAVAILABLE"


def _can_access_scan(user, scan: Scan | None) -> bool:
    if not user or not scan:
        return False
    return scan.user_id == user.id


def _analysis_response_payload(scan: Scan, report: Report, linked_patient: Patient | None) -> dict:
    return {
        "scan": {
            "id": scan.id,
            "scan_type": scan.scan_type,
            "image_url": _public_static_url(scan.original_image_path),
            "processed_image_url": _public_static_url(scan.processed_image_path),
            "patient": _patient_payload(linked_patient),
        },
        "report": {
            "scan_id": report.scan_id,
            "patient_name": report.patient_name,
            "diagnosis": report.diagnosis,
            "severity": report.severity,
            "confidence_pct": report.confidence_pct,
            "doctor_notes": report.doctor_notes,
            "summary_json": report.summary_json,
            "final_json": report.final_json,
            "missing_fields": report.missing_fields or [],
            "ai_source": report.ai_source,
            "ai_warning": report.ai_warning,
        },
    }


def _upsert_report_from_ai(scan: Scan, gemini: dict, groq: dict) -> tuple[Report, Patient | None]:
    gemini_json = gemini["result"]
    summary_json = groq["result"]
    if not isinstance(summary_json, dict):
        raise AIContractError("AI response invalid. Retry analysis.")

    diagnosis = _diagnosis_from_condition(gemini_json.get("suspected_condition", "other"))
    severity = gemini_json.get("severity", "unknown")
    confidence = int(gemini_json.get("confidence_pct", 0) or 0)
    confidence = max(0, min(100, confidence))
    warning_parts = [w for w in [gemini.get("warning"), groq.get("warning")] if w]

    ai_summary_text = _compose_ai_summary_text(
        summary_json=summary_json,
        gemini_json=gemini_json,
        diagnosis=diagnosis,
        severity=severity,
        confidence_pct=confidence,
    )
    summary_json["ai_summary_text"] = ai_summary_text

    if gemini.get("source") == "real" and groq.get("source") == "real":
        if _summary_has_mock_markers(summary_json):
            raise AIContractError("Live AI summary contained mock/demo wording.")

    report = Report.query.filter_by(scan_id=scan.id).first()
    if not report:
        report = Report(scan_id=scan.id)
        db.session.add(report)

    report.ai_json = gemini_json
    report.summary_json = summary_json
    report.missing_fields = summary_json.get("missing_fields", [])
    linked_patient = scan.patient_link.patient if scan.patient_link else None
    if linked_patient and not (report.patient_name or "").strip():
        report.patient_name = linked_patient.full_name
    report.diagnosis = diagnosis
    report.severity = severity
    report.confidence_pct = confidence
    report.ai_source = "real" if gemini["source"] == "real" and groq["source"] == "real" else "mock"
    report.ai_warning = " | ".join(warning_parts) if warning_parts else None

    final_json = dict(report.final_json or {})
    final_json.setdefault("doctor_review_text", "")
    final_json.setdefault("patient_summary_text", "")
    report.final_json = final_json
    scan.analyze_status = "completed"
    return report, linked_patient


def reanalyze_scan_live_record(scan: Scan) -> tuple[Report, Patient | None]:
    gemini = analyze_scan(scan.processed_image_path, scan.scan_type, force_live=True)
    gemini_json = gemini["result"]
    groq = generate_summary(gemini_json, scan.scan_type, force_live=True)
    return _upsert_report_from_ai(scan, gemini, groq)


@scan_bp.post("")
@login_required
def upload_scan():
    user = get_current_user()
    scan_type = (request.form.get("scan_type") or "").lower().strip()
    patient_id_raw = (request.form.get("patient_id") or "").strip()
    file = request.files.get("file")

    if scan_type not in VALID_SCAN_TYPES:
        return jsonify({"error": "scan_type must be one of: xray, ct, or mri"}), 400
    if not patient_id_raw:
        return jsonify({"error": "patient_id is required"}), 400
    try:
        patient_id = int(patient_id_raw)
    except ValueError:
        return jsonify({"error": "patient_id must be an integer"}), 400

    patient = Patient.query.filter_by(
        id=patient_id,
        owner_user_id=user.id,
        is_active=True,
    ).first()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    if not file:
        return jsonify({"error": "Image file is required"}), 400

    filename = secure_filename(file.filename or "")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Only .png, .jpg, .jpeg are supported"}), 400

    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{uuid.uuid4().hex}{ext}"
    file.save(saved_path)

    try:
        processed_path = preprocess_image(saved_path, upload_dir)
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        return jsonify({"error": f"Failed preprocessing image: {exc}"}), 400

    scan = Scan(
        user_id=user.id,
        scan_type=scan_type,
        original_image_path=str(saved_path),
        processed_image_path=str(processed_path),
    )
    db.session.add(scan)
    db.session.flush()
    link = ScanPatientLink(scan_id=scan.id, patient_id=patient.id)
    db.session.add(link)
    db.session.commit()

    return jsonify(
        {
            "scan": {
                "id": scan.id,
                "scan_type": scan.scan_type,
                "image_url": _public_static_url(scan.original_image_path),
                "processed_image_url": _public_static_url(scan.processed_image_path),
                "analyze_status": scan.analyze_status,
                "patient": _patient_payload(patient),
            }
        }
    )


@scan_bp.post("/<int:scan_id>/analyze")
@login_required
def analyze(scan_id: int):
    user = get_current_user()
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        return jsonify({"error": "Scan not found"}), 404

    try:
        gemini = analyze_scan(scan.processed_image_path, scan.scan_type)
        gemini_json = gemini["result"]
        groq = generate_summary(gemini_json, scan.scan_type)
        summary_json = groq["result"]
    except NonMedicalImageError:
        return (
            jsonify(
                {
                    "error": "Upload a valid medical X-ray/CT/MRI scan image.",
                    "code": "NON_MEDICAL_IMAGE",
                }
            ),
            422,
        )
    except AIServiceUnavailableError as exc:
        if not current_app.config.get("AI_FAILOVER_TO_SAFE_MOCK", False):
            message = str(exc).strip() or "AI service unavailable. Check API keys/network and retry."
            return (
                jsonify(
                    {
                        "error": message,
                        "code": _ai_unavailable_code(message),
                    }
                ),
                503,
            )
        gemini = {
            "result": _safe_fallback_scan(scan.scan_type, str(exc)),
            "source": "mock",
            "warning": (
                "Live AI unavailable. Safe fallback report generated (non-diagnostic)."
            ),
        }
        gemini_json = gemini["result"]
        groq = {"result": _safe_fallback_summary(), "source": "mock", "warning": None}
        summary_json = groq["result"]
    except AIContractError:
        return (
            jsonify(
                {
                    "error": "AI response invalid. Retry analysis.",
                    "code": "AI_RESPONSE_INVALID",
                }
            ),
            502,
        )

    try:
        report, linked_patient = _upsert_report_from_ai(scan, gemini, groq)
    except AIContractError:
        return (
            jsonify(
                {
                    "error": "AI response invalid. Retry analysis.",
                    "code": "AI_RESPONSE_INVALID",
                }
            ),
            502,
        )

    db.session.commit()
    return jsonify(_analysis_response_payload(scan, report, linked_patient))


@scan_bp.post("/<int:scan_id>/reanalyze-live")
@login_required
def reanalyze_live(scan_id: int):
    user = get_current_user()
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        return jsonify({"error": "Scan not found"}), 404

    try:
        report, linked_patient = reanalyze_scan_live_record(scan)
    except NonMedicalImageError:
        return (
            jsonify(
                {
                    "error": "Upload a valid medical X-ray/CT/MRI scan image.",
                    "code": "NON_MEDICAL_IMAGE",
                }
            ),
            422,
        )
    except AIServiceUnavailableError as exc:
        message = str(exc).strip() or "AI service unavailable. Check API keys/network and retry."
        return (
            jsonify(
                {
                    "error": message,
                    "code": _ai_unavailable_code(message),
                }
            ),
            503,
        )
    except AIContractError:
        return (
            jsonify(
                {
                    "error": "AI response invalid. Retry analysis.",
                    "code": "AI_RESPONSE_INVALID",
                }
            ),
            502,
        )

    db.session.commit()
    return jsonify(_analysis_response_payload(scan, report, linked_patient))


@scan_bp.get("/<int:scan_id>")
@login_required
def get_scan(scan_id: int):
    user = get_current_user()
    scan = db.session.get(Scan, scan_id)
    if not _can_access_scan(user, scan):
        return jsonify({"error": "Scan not found"}), 404
    linked_patient = scan.patient_link.patient if scan.patient_link else None
    return jsonify(
        {
            "scan": {
                "id": scan.id,
                "scan_type": scan.scan_type,
                "image_url": _public_static_url(scan.original_image_path),
                "processed_image_url": _public_static_url(scan.processed_image_path),
                "analyze_status": scan.analyze_status,
                "patient": _patient_payload(linked_patient),
            }
        }
    )

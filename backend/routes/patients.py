import re
import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from auth_utils import get_current_user, login_required, require_role
from extensions import db
from models.patient import Patient


patients_bp = Blueprint("patients", __name__, url_prefix="/api/patients")

VALID_GENDERS = {"male", "female", "other", "unknown"}
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{6,20}$")


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


def _patient_payload(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "owner_user_id": patient.owner_user_id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "age": patient.age,
        "gender": patient.gender,
        "phone": patient.phone or "",
        "notes": patient.notes or "",
        "created_at": patient.created_at.isoformat() if patient.created_at else None,
        "updated_at": patient.updated_at.isoformat() if patient.updated_at else None,
    }


def _to_age(value):
    if value is None or value == "":
        return None
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise ValueError("Age must be a number.")
    if age < 0 or age > 120:
        raise ValueError("Age must be between 0 and 120.")
    return age


def _to_gender(value):
    if value is None or value == "":
        return "unknown"
    gender = str(value).strip().lower()
    if gender not in VALID_GENDERS:
        raise ValueError("Gender must be male, female, other, or unknown.")
    return gender


def _to_phone(value):
    if value is None:
        return ""
    phone = str(value).strip()
    if not phone:
        return ""
    if not PHONE_PATTERN.fullmatch(phone):
        raise ValueError("Phone must be 6-20 characters and contain only digits or + - ( ) spaces.")
    return phone


def _get_accessible_patient(user_id: int, patient_id: int) -> Patient | None:
    return Patient.query.filter_by(id=patient_id, is_active=True, owner_user_id=user_id).first()


def _get_patient_for_admin_action(user_id: int, patient_id: int, user_role: str) -> Patient | None:
    """Get a patient for admin action. Admins can access any patient, doctors only their own."""
    if user_role == "admin":
        return Patient.query.filter_by(id=patient_id, is_active=True).first()
    else:
        return _get_accessible_patient(user_id, patient_id)


@patients_bp.get("")
@login_required
def list_patients():
    user = get_current_user()
    query = (request.args.get("query") or "").strip()
    page, page_size = _parse_pagination()

    base = Patient.query.filter_by(is_active=True, owner_user_id=user.id)
    if query:
        like = f"%{query}%"
        base = base.filter(
            or_(
                Patient.patient_code.ilike(like),
                Patient.full_name.ilike(like),
                Patient.phone.ilike(like),
            )
        )

    total = base.count()
    items = (
        base.order_by(Patient.created_at.desc(), Patient.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return jsonify(
        {
            "items": [_patient_payload(patient) for patient in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@patients_bp.post("")
@login_required
def create_patient():
    user = get_current_user()
    payload = request.get_json(silent=True) or {}

    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        return jsonify({"error": "Patient full name is required."}), 400
    if len(full_name) > 120:
        return jsonify({"error": "Patient full name is too long."}), 400

    try:
        age = _to_age(payload.get("age"))
        gender = _to_gender(payload.get("gender"))
        phone = _to_phone(payload.get("phone"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    notes = str(payload.get("notes") or "").strip()
    patient = Patient(
        owner_user_id=user.id,
        patient_code=f"ETA-TMP-{uuid.uuid4().hex[:8].upper()}",
        full_name=full_name,
        age=age,
        gender=gender,
        phone=phone,
        notes=notes,
    )
    db.session.add(patient)
    db.session.flush()
    patient.patient_code = f"ETA-P{patient.id:06d}"
    db.session.commit()
    return jsonify({"patient": _patient_payload(patient)}), 201


@patients_bp.get("/<int:patient_id>")
@login_required
def get_patient(patient_id: int):
    user = get_current_user()
    patient = _get_accessible_patient(user.id, patient_id)
    if not patient:
        return jsonify({"error": "Patient not found."}), 404
    return jsonify({"patient": _patient_payload(patient)})


@patients_bp.put("/<int:patient_id>")
@login_required
def update_patient(patient_id: int):
    user = get_current_user()
    patient = _get_accessible_patient(user.id, patient_id)
    if not patient:
        return jsonify({"error": "Patient not found."}), 404

    payload = request.get_json(silent=True) or {}

    if "full_name" in payload:
        full_name = (payload.get("full_name") or "").strip()
        if not full_name:
            return jsonify({"error": "Patient full name is required."}), 400
        if len(full_name) > 120:
            return jsonify({"error": "Patient full name is too long."}), 400
        patient.full_name = full_name

    try:
        if "age" in payload:
            patient.age = _to_age(payload.get("age"))
        if "gender" in payload:
            patient.gender = _to_gender(payload.get("gender"))
        if "phone" in payload:
            patient.phone = _to_phone(payload.get("phone"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if "notes" in payload:
        patient.notes = str(payload.get("notes") or "").strip()

    db.session.commit()
    return jsonify({"patient": _patient_payload(patient)})


@patients_bp.delete("/<int:patient_id>")
@login_required
def archive_patient(patient_id: int):
    user = get_current_user()
    patient = _get_patient_for_admin_action(user.id, patient_id, user.role)
    if not patient:
        return jsonify({"error": "Patient not found."}), 404

    patient.is_active = False
    db.session.commit()
    return jsonify({"ok": True})

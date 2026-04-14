import json
import mimetypes
from pathlib import Path

from flask import current_app

from .errors import AIContractError, AIServiceUnavailableError, NonMedicalImageError

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


VALID_SCAN_TYPES = {"xray", "ct", "mri"}
VALID_CONDITIONS = {
    "bone_fracture",
    "brain_hemorrhage",
    "pneumothorax",
    "no_clear_finding",
    "other",
}
VALID_SEVERITIES = {"critical", "moderate", "mild", "unknown"}
REQUIRED_KEYS = {
    "scan_type",
    "body_region",
    "primary_findings",
    "suspected_condition",
    "severity",
    "confidence_pct",
    "notes_for_doctor",
    "limitations",
    "is_medical_scan",
    "rejection_reason",
}


def _mock_response(scan_type: str) -> dict:
    safe_scan_type = scan_type if scan_type in VALID_SCAN_TYPES else "xray"
    return {
        "scan_type": safe_scan_type,
        "body_region": "unknown",
        "primary_findings": [
            "Mock mode output only. No clinical image inference was performed.",
        ],
        "suspected_condition": "no_clear_finding",
        "severity": "unknown",
        "confidence_pct": 12,
        "notes_for_doctor": "USE_MOCK_AI is enabled. This non-diagnostic output is for UI/demo flow only.",
        "limitations": "Mock output; not derived from real medical-image analysis.",
        "is_medical_scan": True,
        "rejection_reason": "",
    }


def _to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _coerce_findings(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    return []


def _strip_json(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def _safe_json(raw_text: str) -> dict:
    cleaned = _strip_json(raw_text)
    try:
        parsed = json.loads(cleaned)
    except Exception as exc:
        raise AIContractError("Gemini returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise AIContractError("Gemini response JSON must be an object.")
    return parsed


def _build_prompt(scan_type: str) -> str:
    modality_guidance = {
        "xray": (
            "For X-ray: focus on visible fracture/dislocation patterns, pleural air/fluid signs, "
            "and clearly visible trauma-related opacities."
        ),
        "ct": (
            "For CT: prioritize acute hemorrhage patterns, mass effect/midline shift clues, "
            "pneumothorax/hemothorax signs, and obvious solid-organ injury indicators when visible."
        ),
        "mri": (
            "For MRI: focus on soft-tissue edema, ligament/tendon disruption clues, marrow/cord signal "
            "abnormalities, and sequence-limited uncertainty notes when confidence is low."
        ),
    }.get(scan_type, "Use modality-appropriate trauma triage language.")

    return f"""
You are a medical imaging triage assistant.
Analyze this {scan_type} trauma scan and return ONLY valid JSON.
No markdown, no explanations.
{modality_guidance}

Required keys:
scan_type, body_region, primary_findings, suspected_condition, severity, confidence_pct, notes_for_doctor, limitations, is_medical_scan, rejection_reason

Rules:
- scan_type must be one of: xray, ct, or mri
- suspected_condition must be one of bone_fracture|brain_hemorrhage|pneumothorax|no_clear_finding|other
- severity must be one of critical|moderate|mild|unknown
- confidence_pct must be integer 0..100
- is_medical_scan must be true only if this is clearly a real medical scan image (X-ray/CT/MRI).
- if image is non-medical, screenshot, poster, selfie, or unrelated: set is_medical_scan=false and provide rejection_reason.
- if uncertain on findings but medical image is valid: set suspected_condition=no_clear_finding and confidence_pct <= 40.
- when is_medical_scan=true, rejection_reason must be an empty string.
- limitations must describe uncertainty and modality constraints when confidence is low.

Output template:
{{
  "scan_type": "{scan_type}",
  "body_region": "string",
  "primary_findings": ["string"],
  "suspected_condition": "bone_fracture|brain_hemorrhage|pneumothorax|no_clear_finding|other",
  "severity": "critical|moderate|mild|unknown",
  "confidence_pct": 0,
  "notes_for_doctor": "string",
  "limitations": "string",
  "is_medical_scan": true,
  "rejection_reason": ""
}}
""".strip()


def _validate_contract(data: dict, expected_scan_type: str) -> dict:
    missing = sorted(REQUIRED_KEYS - set(data.keys()))
    if missing:
        raise AIContractError(f"Gemini response missing keys: {', '.join(missing)}.")

    is_medical_scan = _to_bool(data.get("is_medical_scan"))
    if is_medical_scan is None:
        raise AIContractError("is_medical_scan must be boolean.")

    scan_type = str(data.get("scan_type", "")).strip().lower()
    if scan_type not in VALID_SCAN_TYPES:
        if is_medical_scan:
            raise AIContractError("Invalid scan_type from Gemini.")
        scan_type = expected_scan_type if expected_scan_type in VALID_SCAN_TYPES else "xray"
    if is_medical_scan and expected_scan_type in VALID_SCAN_TYPES and scan_type != expected_scan_type:
        raise AIContractError("Gemini returned mismatched scan_type.")

    suspected_condition = str(data.get("suspected_condition", "")).strip().lower()
    if suspected_condition not in VALID_CONDITIONS:
        if is_medical_scan:
            raise AIContractError("Invalid suspected_condition from Gemini.")
        suspected_condition = "no_clear_finding"

    severity = str(data.get("severity", "")).strip().lower()
    if severity not in VALID_SEVERITIES:
        if is_medical_scan:
            raise AIContractError("Invalid severity from Gemini.")
        severity = "unknown"

    try:
        confidence = int(data.get("confidence_pct"))
    except Exception as exc:
        if is_medical_scan:
            raise AIContractError("confidence_pct must be an integer.") from exc
        confidence = 0
    if confidence < 0 or confidence > 100:
        if is_medical_scan:
            raise AIContractError("confidence_pct must be in range 0..100.")
        confidence = max(0, min(100, confidence))

    rejection_reason = str(data.get("rejection_reason", "")).strip()
    if is_medical_scan and rejection_reason:
        raise AIContractError("rejection_reason must be empty when is_medical_scan=true.")
    if not is_medical_scan and not rejection_reason:
        rejection_reason = "Uploaded image is not a valid medical scan."

    findings = _coerce_findings(data.get("primary_findings", []))

    normalized = {
        "scan_type": scan_type,
        "body_region": str(data.get("body_region", "unknown")).strip() or "unknown",
        "primary_findings": findings,
        "suspected_condition": suspected_condition,
        "severity": severity,
        "confidence_pct": confidence,
        "notes_for_doctor": str(data.get("notes_for_doctor", "")).strip(),
        "limitations": str(data.get("limitations", "")).strip(),
        "is_medical_scan": is_medical_scan,
        "rejection_reason": rejection_reason,
    }
    return normalized


def _repair_response(client, model: str, expected_scan_type: str, raw_text: str) -> dict:
    repair_prompt = f"""
Rewrite this model output into strict valid JSON only.
Do not add markdown.
Ensure keys: {", ".join(sorted(REQUIRED_KEYS))}
scan_type must be "{expected_scan_type}".
If content indicates non-medical image, set is_medical_scan=false, suspected_condition=no_clear_finding, severity=unknown.
Original output:
{raw_text}
""".strip()
    repaired = client.models.generate_content(model=model, contents=[repair_prompt])
    return _safe_json(repaired.text)


def _service_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    if "resource_exhausted" in text or "quota" in text or "429" in text:
        return "Gemini quota exceeded. Update Gemini billing/quota and retry."
    if ("api key" in text and "invalid" in text) or "permission denied" in text or "unauthenticated" in text:
        return "Gemini authentication failed. Check GEMINI_API_KEY."
    if "timeout" in text or "timed out" in text or "deadline exceeded" in text:
        return "Gemini request timed out. Check network and retry."
    return "Gemini service is unavailable. Please retry."


def analyze_scan(image_path: str | Path, scan_type: str, force_live: bool = False) -> dict:
    normalized_scan_type = str(scan_type).strip().lower()
    force_mock = current_app.config["USE_MOCK_AI"]
    api_key = current_app.config["GEMINI_API_KEY"]
    model = current_app.config["GEMINI_MODEL"]

    if force_mock and not force_live:
        return {
            "result": _mock_response(normalized_scan_type),
            "source": "mock",
            "warning": "Mock mode enabled. Output is non-diagnostic.",
        }

    if not api_key or genai is None or types is None:
        raise AIServiceUnavailableError("Gemini is unavailable. Configure GEMINI_API_KEY and SDK.")

    try:
        path = Path(image_path)
        image_bytes = path.read_bytes()
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(normalized_scan_type)
        response = client.models.generate_content(
            model=model,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
        )
        raw_text = response.text or ""
        try:
            parsed = _safe_json(raw_text)
            validated = _validate_contract(parsed, normalized_scan_type)
        except AIContractError:
            repaired = _repair_response(client, model, normalized_scan_type, raw_text)
            validated = _validate_contract(repaired, normalized_scan_type)
        if not validated["is_medical_scan"]:
            reason = validated["rejection_reason"] or "Uploaded image is not a valid medical scan."
            raise NonMedicalImageError(reason)
        return {"result": validated, "source": "real", "warning": None}
    except (NonMedicalImageError, AIContractError):
        raise
    except Exception as exc:
        raise AIServiceUnavailableError(_service_error_message(exc)) from exc

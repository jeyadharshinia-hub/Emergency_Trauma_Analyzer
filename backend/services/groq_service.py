import json

import requests
from flask import current_app

from .errors import AIContractError, AIServiceUnavailableError


REQUIRED_KEYS = {
    "doctor_summary_en",
    "doctor_summary_ta",
    "patient_summary_en",
    "patient_summary_ta",
    "missing_fields",
    "safety_disclaimer_en",
    "safety_disclaimer_ta",
}


def _mock_summary() -> dict:
    return {
        "doctor_summary_en": (
            "Mock mode summary only. No diagnostic conclusion generated from image analysis."
        ),
        "doctor_summary_ta": (
            "இது டெமோ mock சுருக்கம் மட்டும். பட பகுப்பாய்விலிருந்து மருத்துவ முடிவு வழங்கப்படவில்லை."
        ),
        "patient_summary_en": (
            "Demo report only. Please use live AI services for clinical assistance."
        ),
        "patient_summary_ta": (
            "இது டெமோ அறிக்கை மட்டும். மருத்துவ உதவிக்காக live AI சேவையை பயன்படுத்தவும்."
        ),
        "missing_fields": ["Age", "Gender", "Injury mechanism", "Symptoms", "Vitals"],
        "safety_disclaimer_en": (
            "AI-assisted screening only. Final clinical decision must be made by a qualified doctor."
        ),
        "safety_disclaimer_ta": (
            "இது AI உதவியுள்ள ஆரம்ப பரிசோதனை மட்டும். இறுதி மருத்துவ முடிவை தகுதியான மருத்துவர் மட்டுமே எடுக்க வேண்டும்."
        ),
    }


def _validate_contract(data: dict) -> dict:
    if not isinstance(data, dict):
        raise AIContractError("Groq response must be a JSON object.")

    missing = sorted(REQUIRED_KEYS - set(data.keys()))
    if missing:
        raise AIContractError(f"Groq response missing keys: {', '.join(missing)}.")

    fields = data.get("missing_fields", [])
    if not isinstance(fields, list):
        raise AIContractError("missing_fields must be an array.")

    return {
        "doctor_summary_en": str(data.get("doctor_summary_en", "")).strip(),
        "doctor_summary_ta": str(data.get("doctor_summary_ta", "")).strip(),
        "patient_summary_en": str(data.get("patient_summary_en", "")).strip(),
        "patient_summary_ta": str(data.get("patient_summary_ta", "")).strip(),
        "missing_fields": [str(item) for item in fields if str(item).strip()],
        "safety_disclaimer_en": str(data.get("safety_disclaimer_en", "")).strip(),
        "safety_disclaimer_ta": str(data.get("safety_disclaimer_ta", "")).strip(),
    }


def generate_summary(gemini_json: dict, scan_type: str, force_live: bool = False) -> dict:
    force_mock = current_app.config["USE_MOCK_AI"]
    api_key = current_app.config["GROQ_API_KEY"]
    model = current_app.config["GROQ_MODEL"]

    if force_mock and not force_live:
        return {
            "result": _mock_summary(),
            "source": "mock",
            "warning": "Mock mode enabled. Summary is non-diagnostic.",
        }

    if not api_key:
        raise AIServiceUnavailableError("Groq is unavailable. Configure GROQ_API_KEY.")

    modality_guidance = {
        "xray": (
            "X-ray summary should mention visible fracture/dislocation/pleural trauma clues when present."
        ),
        "ct": (
            "CT summary should mention intracranial bleed concerns, mass effect, chest air/fluid trauma signs, "
            "or organ injury cues when supported by findings."
        ),
        "mri": (
            "MRI summary should emphasize soft-tissue/ligament/marrow/cord signal findings and sequence-limited uncertainty."
        ),
    }.get(str(scan_type).strip().lower(), "Use modality-appropriate trauma interpretation language.")

    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return ONLY valid JSON. Draft short bilingual doctor and patient summaries "
                    "for emergency trauma reporting. Never mention mock/demo unless explicitly present in source findings."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Scan type: {scan_type}\n"
                    f"Modality guidance: {modality_guidance}\n"
                    f"Gemini findings: {json.dumps(gemini_json, ensure_ascii=False)}\n"
                    "Return keys: doctor_summary_en, doctor_summary_ta, patient_summary_en, "
                    "patient_summary_ta, missing_fields, safety_disclaimer_en, safety_disclaimer_ta.\n"
                    "Doctor summary must include urgency impression and confidence caveat.\n"
                    "Patient summary must be plain-language and safe.\n"
                    "Do not output markdown."
                ),
            },
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 401:
            raise AIServiceUnavailableError("Groq authentication failed. Check GROQ_API_KEY.") from exc
        if status == 429:
            raise AIServiceUnavailableError("Groq rate limit exceeded. Retry shortly.") from exc
        raise AIServiceUnavailableError("Groq service is unavailable. Please retry.") from exc
    except Exception as exc:
        raise AIServiceUnavailableError("Groq service is unavailable. Please retry.") from exc

    try:
        raw = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
    except Exception as exc:
        raise AIContractError("Groq returned invalid JSON content.") from exc

    validated = _validate_contract(parsed)
    return {"result": validated, "source": "real", "warning": None}

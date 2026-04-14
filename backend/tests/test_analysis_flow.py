import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ["DATABASE_URL"] = "sqlite:///eta_test_suite.db"
os.environ["SECRET_KEY"] = "eta-test-secret"
os.environ["USE_MOCK_AI"] = "true"

from app import create_app  # noqa: E402
from extensions import bcrypt, db  # noqa: E402
from models.patient import Patient  # noqa: E402
from models.report import Report  # noqa: E402
from models.scan import Scan  # noqa: E402
from models.user import User  # noqa: E402
from routes.auth import seed_demo_user  # noqa: E402
from services.errors import (  # noqa: E402
    AIContractError,
    AIServiceUnavailableError,
    NonMedicalImageError,
)


class AnalysisFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        self.tempdir = tempfile.TemporaryDirectory()
        self.app.config["UPLOAD_DIR"] = Path(self.tempdir.name) / "uploads"
        self.app.config["REPORT_DIR"] = Path(self.tempdir.name) / "reports"
        self.app.config["GEMINI_API_KEY"] = ""
        self.app.config["GROQ_API_KEY"] = ""
        self.app.config["USE_MOCK_AI"] = True
        self.app.config["AI_FAILOVER_TO_SAFE_MOCK"] = False
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()
            seed_demo_user()
        self._login_doctor()

    def tearDown(self):
        self.tempdir.cleanup()

    def _login(self, username: str, password: str):
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["user"]

    def _login_doctor(self):
        return self._login("demo_doctor", "demo123")

    def _login_admin(self):
        return self._login("admin", "admin123")

    @staticmethod
    def _sample_image_bytes() -> io.BytesIO:
        image = Image.new("RGB", (240, 180), color="white")
        stream = io.BytesIO()
        image.save(stream, format="JPEG")
        stream.seek(0)
        return stream

    def _create_patient(self, full_name: str = "Test Patient") -> int:
        payload = {
            "full_name": full_name,
            "age": 32,
            "gender": "male",
            "phone": "+919999999999",
            "notes": "Initial test patient",
        }
        response = self.client.post("/api/patients", json=payload)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["patient"]["id"]

    def _upload_scan(self, scan_type: str = "xray", patient_id: int | None = None) -> int:
        target_patient_id = patient_id or self._create_patient()
        payload = {
            "scan_type": scan_type,
            "patient_id": str(target_patient_id),
            "file": (self._sample_image_bytes(), "scan.jpg"),
        }
        response = self.client.post(
            "/api/scans",
            data=payload,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["scan"]["id"]

    def test_quick_login_returns_doctor_account(self):
        response = self.client.post("/api/auth/quick-login")
        self.assertEqual(response.status_code, 200, response.get_data())
        user = response.get_json()["user"]
        self.assertEqual(user["username"], "demo_doctor")
        self.assertEqual(user["role"], "doctor")

    def test_quick_login_returns_admin_account(self):
        response = self.client.post("/api/auth/quick-login", json={"role": "admin"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        user = response.get_json()["user"]
        self.assertEqual(user["username"], "admin")
        self.assertEqual(user["role"], "admin")

    def test_seed_keeps_demo_doctor_and_admin_users(self):
        with self.app.app_context():
            users = User.query.order_by(User.username.asc()).all()
            self.assertEqual(len(users), 2)
            self.assertEqual(users[0].username, "admin")
            self.assertEqual(users[0].role, "admin")
            self.assertEqual(users[1].username, "demo_doctor")
            self.assertEqual(users[1].role, "doctor")

    def test_admin_routes_require_admin_role(self):
        response = self.client.get("/api/admin/stats")
        self.assertEqual(response.status_code, 403, response.get_data(as_text=True))

        self.client.post("/api/auth/logout")
        self._login_admin()
        allowed = self.client.get("/api/admin/stats")
        self.assertEqual(allowed.status_code, 200, allowed.get_data(as_text=True))

    def test_admin_can_manage_doctors_and_view_activity(self):
        patient_id = self._create_patient(full_name="Admin Activity Patient")
        scan_id = self._upload_scan(scan_type="ct", patient_id=patient_id)
        analyze = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(analyze.status_code, 200, analyze.get_data(as_text=True))

        self.client.post("/api/auth/logout")
        self._login_admin()

        users_res = self.client.get("/api/admin/users")
        self.assertEqual(users_res.status_code, 200, users_res.get_data(as_text=True))
        users_payload = users_res.get_json()
        self.assertTrue(any(user["username"] == "demo_doctor" for user in users_payload["users"]))

        create_res = self.client.post(
            "/api/admin/users",
            json={"username": "doctor_admin_created", "password": "doctor123"},
        )
        self.assertEqual(create_res.status_code, 201, create_res.get_data(as_text=True))
        self.assertEqual(create_res.get_json()["user"]["role"], "doctor")

        activity_res = self.client.get("/api/admin/activity")
        self.assertEqual(activity_res.status_code, 200, activity_res.get_data(as_text=True))
        activity_items = activity_res.get_json()["items"]
        self.assertTrue(any(item["scan_id"] == scan_id for item in activity_items))

    def test_admin_pdf_download_returns_valid_pdf(self):
        patient_id = self._create_patient(full_name="Admin PDF Patient")
        scan_id = self._upload_scan(scan_type="xray", patient_id=patient_id)
        analyze = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(analyze.status_code, 200, analyze.get_data(as_text=True))

        self.client.post("/api/auth/logout")
        self._login_admin()

        response = self.client.get(f"/api/admin/reports/{scan_id}/pdf", buffered=True)
        self.assertEqual(response.status_code, 200, response.get_data())
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("eta_report_Admin_PDF_Patient_", response.headers.get("Content-Disposition", ""))
        self.assertTrue(response.get_data().startswith(b"%PDF-"))
        response.close()

    def test_mock_mode_success_is_safe_non_diagnostic(self):
        self.app.config["USE_MOCK_AI"] = True
        scan_id = self._upload_scan()

        response = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()

        self.assertEqual(data["report"]["diagnosis"], "No Clear Finding")
        self.assertEqual(data["report"]["severity"], "unknown")
        self.assertLessEqual(data["report"]["confidence_pct"], 25)
        self.assertEqual(data["report"]["ai_source"], "mock")

        with self.app.app_context():
            report = Report.query.filter_by(scan_id=scan_id).first()
            self.assertIsNotNone(report)
            self.assertEqual(report.ai_json["suspected_condition"], "no_clear_finding")

    def test_live_success_with_stubbed_services_creates_report(self):
        self.app.config["USE_MOCK_AI"] = False
        scan_id = self._upload_scan(scan_type="ct")

        gemini_result = {
            "result": {
                "scan_type": "ct",
                "body_region": "head",
                "primary_findings": ["Focal density"],
                "suspected_condition": "brain_hemorrhage",
                "severity": "critical",
                "confidence_pct": 87,
                "notes_for_doctor": "Urgent neuro evaluation",
                "limitations": "Initial AI screen",
                "is_medical_scan": True,
                "rejection_reason": "",
            },
            "source": "real",
            "warning": None,
        }
        groq_result = {
            "result": {
                "doctor_summary_en": "Potential critical intracranial finding.",
                "doctor_summary_ta": "மிக கவனிக்க வேண்டிய மூளை உள்ளக கண்டுபிடிப்பு இருக்கலாம்.",
                "patient_summary_en": "Doctor will confirm with urgent review.",
                "patient_summary_ta": "மருத்துவர் உடனடி மதிப்பீட்டில் உறுதி செய்வார்.",
                "missing_fields": ["Vitals"],
                "safety_disclaimer_en": "AI-assisted screening only.",
                "safety_disclaimer_ta": "இது AI உதவியுள்ள ஆரம்ப பரிசோதனை மட்டும்.",
            },
            "source": "real",
            "warning": None,
        }

        with patch("routes.scan.analyze_scan", return_value=gemini_result), patch(
            "routes.scan.generate_summary", return_value=groq_result
        ):
            response = self.client.post(f"/api/scans/{scan_id}/analyze")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()["report"]
        self.assertEqual(payload["diagnosis"], "Possible Brain Hemorrhage")
        self.assertEqual(payload["severity"], "critical")
        self.assertEqual(payload["confidence_pct"], 87)
        self.assertEqual(payload["ai_source"], "real")

    def test_reanalyze_live_updates_report_and_preserves_manual_edits(self):
        scan_id = self._upload_scan(scan_type="mri")
        first = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(first.get_json()["report"]["ai_source"], "mock")

        update = self.client.put(
            f"/api/reports/{scan_id}",
            json={
                "doctor_review_text": "Manual doctor review persists.",
                "patient_summary_text": "Manual patient summary persists.",
            },
        )
        self.assertEqual(update.status_code, 200, update.get_data(as_text=True))

        self.app.config["USE_MOCK_AI"] = False
        gemini_result = {
            "result": {
                "scan_type": "mri",
                "body_region": "spine",
                "primary_findings": ["Soft tissue edema"],
                "suspected_condition": "other",
                "severity": "moderate",
                "confidence_pct": 74,
                "notes_for_doctor": "Correlate with neuro exam",
                "limitations": "Single image frame",
                "is_medical_scan": True,
                "rejection_reason": "",
            },
            "source": "real",
            "warning": None,
        }
        groq_result = {
            "result": {
                "doctor_summary_en": "MRI suggests moderate traumatic soft tissue change.",
                "doctor_summary_ta": "MRIல் மிதமான காயம் தொடர்பான மென்மையான திசு மாற்றம் உள்ளது.",
                "patient_summary_en": "Doctor will confirm findings with clinical exam.",
                "patient_summary_ta": "மருத்துவர் மருத்துவ பரிசோதனையுடன் கண்டுபிடிப்பை உறுதி செய்வார்.",
                "missing_fields": ["Vitals"],
                "safety_disclaimer_en": "AI-assisted screening only.",
                "safety_disclaimer_ta": "இது AI உதவியுள்ள ஆரம்ப பரிசோதனை மட்டும்.",
            },
            "source": "real",
            "warning": None,
        }

        with patch("routes.scan.analyze_scan", return_value=gemini_result) as gemini_patch, patch(
            "routes.scan.generate_summary", return_value=groq_result
        ) as groq_patch:
            response = self.client.post(f"/api/scans/{scan_id}/reanalyze-live")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()["report"]
        self.assertEqual(payload["severity"], "moderate")
        self.assertEqual(payload["confidence_pct"], 74)
        self.assertEqual(payload["ai_source"], "real")
        self.assertTrue(gemini_patch.call_args.kwargs.get("force_live"))
        self.assertTrue(groq_patch.call_args.kwargs.get("force_live"))

        get_report = self.client.get(f"/api/reports/{scan_id}")
        self.assertEqual(get_report.status_code, 200, get_report.get_data(as_text=True))
        merged = get_report.get_json()["report"]
        self.assertEqual(merged["doctor_review_text"], "Manual doctor review persists.")
        self.assertEqual(merged["patient_summary_text"], "Manual patient summary persists.")

    def test_live_summary_with_mock_marker_returns_502(self):
        self.app.config["USE_MOCK_AI"] = False
        scan_id = self._upload_scan(scan_type="ct")

        gemini_result = {
            "result": {
                "scan_type": "ct",
                "body_region": "head",
                "primary_findings": ["Acute density focus"],
                "suspected_condition": "brain_hemorrhage",
                "severity": "critical",
                "confidence_pct": 88,
                "notes_for_doctor": "Urgent neuro eval",
                "limitations": "Initial triage",
                "is_medical_scan": True,
                "rejection_reason": "",
            },
            "source": "real",
            "warning": None,
        }
        groq_result = {
            "result": {
                "doctor_summary_en": "Mock mode summary only. No diagnostic conclusion generated from image analysis.",
                "doctor_summary_ta": "இது டெமோ mock சுருக்கம் மட்டும்.",
                "patient_summary_en": "Demo report only.",
                "patient_summary_ta": "இது டெமோ அறிக்கை மட்டும்.",
                "missing_fields": ["Vitals"],
                "safety_disclaimer_en": "AI-assisted screening only.",
                "safety_disclaimer_ta": "இது AI உதவியுள்ள ஆரம்ப பரிசோதனை மட்டும்.",
            },
            "source": "real",
            "warning": None,
        }

        with patch("routes.scan.analyze_scan", return_value=gemini_result), patch(
            "routes.scan.generate_summary", return_value=groq_result
        ):
            response = self.client.post(f"/api/scans/{scan_id}/analyze")

        self.assertEqual(response.status_code, 502, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual(body["code"], "AI_RESPONSE_INVALID")

    def test_non_medical_image_returns_422_and_no_report(self):
        self.app.config["USE_MOCK_AI"] = False
        scan_id = self._upload_scan()

        with patch(
            "routes.scan.analyze_scan",
            side_effect=NonMedicalImageError("not medical"),
        ):
            response = self.client.post(f"/api/scans/{scan_id}/analyze")

        self.assertEqual(response.status_code, 422)
        body = response.get_json()
        self.assertEqual(body["code"], "NON_MEDICAL_IMAGE")

        with self.app.app_context():
            report = Report.query.filter_by(scan_id=scan_id).first()
            self.assertIsNone(report)

    def test_missing_keys_in_live_mode_returns_503(self):
        self.app.config["USE_MOCK_AI"] = False
        self.app.config["AI_FAILOVER_TO_SAFE_MOCK"] = False
        self.app.config["GEMINI_API_KEY"] = ""
        scan_id = self._upload_scan()

        response = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertEqual(body["code"], "AI_UNAVAILABLE")

    def test_missing_keys_with_failover_returns_safe_result(self):
        self.app.config["USE_MOCK_AI"] = False
        self.app.config["AI_FAILOVER_TO_SAFE_MOCK"] = True
        self.app.config["GEMINI_API_KEY"] = ""
        scan_id = self._upload_scan()

        response = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual(body["report"]["diagnosis"], "No Clear Finding")
        self.assertEqual(body["report"]["severity"], "unknown")
        self.assertEqual(body["report"]["ai_source"], "mock")
        self.assertIn("Safe fallback report generated", body["report"]["ai_warning"])

    def test_ai_contract_error_returns_502(self):
        self.app.config["USE_MOCK_AI"] = False
        scan_id = self._upload_scan()

        with patch("routes.scan.analyze_scan", side_effect=AIContractError("bad contract")):
            response = self.client.post(f"/api/scans/{scan_id}/analyze")

        self.assertEqual(response.status_code, 502)
        body = response.get_json()
        self.assertEqual(body["code"], "AI_RESPONSE_INVALID")

    def test_ai_quota_error_maps_to_specific_code(self):
        self.app.config["USE_MOCK_AI"] = False
        self.app.config["AI_FAILOVER_TO_SAFE_MOCK"] = False
        scan_id = self._upload_scan()

        with patch(
            "routes.scan.analyze_scan",
            side_effect=AIServiceUnavailableError(
                "Gemini quota exceeded. Update Gemini billing/quota and retry."
            ),
        ):
            response = self.client.post(f"/api/scans/{scan_id}/analyze")

        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertEqual(body["code"], "AI_QUOTA_EXCEEDED")

    def test_upload_requires_patient_id(self):
        payload = {
            "scan_type": "xray",
            "file": (self._sample_image_bytes(), "scan.jpg"),
        }
        response = self.client.post(
            "/api/scans",
            data=payload,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("patient_id is required", response.get_data(as_text=True))

    def test_upload_with_foreign_patient_is_rejected(self):
        with self.app.app_context():
            doctor = User.query.filter_by(username="demo_doctor").first()
            other_user = User(
                username="legacy_other",
                password_hash=bcrypt.generate_password_hash("doctor123").decode("utf-8"),
                role="doctor",
            )
            db.session.add(other_user)
            db.session.flush()
            foreign_patient = Patient(
                owner_user_id=other_user.id,
                patient_code="ETA-P999999",
                full_name="Foreign Patient",
                age=31,
                gender="male",
            )
            db.session.add(foreign_patient)
            db.session.commit()
            self.assertNotEqual(foreign_patient.owner_user_id, doctor.id)
            foreign_patient_id = foreign_patient.id

        payload = {
            "scan_type": "xray",
            "patient_id": str(foreign_patient_id),
            "file": (self._sample_image_bytes(), "scan.jpg"),
        }
        response = self.client.post(
            "/api/scans",
            data=payload,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Patient not found", response.get_data(as_text=True))

    def test_patient_management_crud_and_archive(self):
        create_res = self.client.post(
            "/api/patients",
            json={"full_name": "Patient One", "age": 40, "gender": "female", "phone": "9999999999"},
        )
        self.assertEqual(create_res.status_code, 201, create_res.get_data(as_text=True))
        patient = create_res.get_json()["patient"]
        patient_id = patient["id"]

        list_res = self.client.get("/api/patients")
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(item["id"] == patient_id for item in list_res.get_json()["items"]))

        update_res = self.client.put(
            f"/api/patients/{patient_id}",
            json={"notes": "Updated notes", "phone": "+91 98765 43210"},
        )
        self.assertEqual(update_res.status_code, 200, update_res.get_data(as_text=True))

        archive_res = self.client.delete(f"/api/patients/{patient_id}")
        self.assertEqual(archive_res.status_code, 200)
        list_res_after = self.client.get("/api/patients")
        self.assertFalse(any(item["id"] == patient_id for item in list_res_after.get_json()["items"]))

    def test_report_history_scope_filters_and_query(self):
        own_patient_id = self._create_patient(full_name="History Patient")
        own_scan_with_report = self._upload_scan(scan_type="xray", patient_id=own_patient_id)
        analyze_res = self.client.post(f"/api/scans/{own_scan_with_report}/analyze")
        self.assertEqual(analyze_res.status_code, 200, analyze_res.get_data(as_text=True))
        own_scan_without_report = self._upload_scan(scan_type="ct", patient_id=own_patient_id)

        history_res = self.client.get("/api/reports/history", query_string={"page_size": 100})
        self.assertEqual(history_res.status_code, 200, history_res.get_data(as_text=True))
        history_payload = history_res.get_json()
        returned_ids = {item["scan_id"] for item in history_payload["items"]}
        self.assertIn(own_scan_with_report, returned_ids)
        self.assertIn(own_scan_without_report, returned_ids)

        by_scan_id = {item["scan_id"]: item for item in history_payload["items"]}
        self.assertTrue(by_scan_id[own_scan_with_report]["has_report"])
        self.assertIsNotNone(by_scan_id[own_scan_with_report]["report"])
        self.assertFalse(by_scan_id[own_scan_without_report]["has_report"])
        self.assertIsNone(by_scan_id[own_scan_without_report]["report"])

        with_report_res = self.client.get(
            "/api/reports/history",
            query_string={"status": "with_report", "page_size": 100},
        )
        self.assertEqual(with_report_res.status_code, 200, with_report_res.get_data(as_text=True))
        with_report_ids = {item["scan_id"] for item in with_report_res.get_json()["items"]}
        self.assertEqual(with_report_ids, {own_scan_with_report})

        no_report_res = self.client.get(
            "/api/reports/history",
            query_string={"status": "no_report", "page_size": 100},
        )
        self.assertEqual(no_report_res.status_code, 200, no_report_res.get_data(as_text=True))
        no_report_ids = {item["scan_id"] for item in no_report_res.get_json()["items"]}
        self.assertEqual(no_report_ids, {own_scan_without_report})

        diagnosis_query_res = self.client.get(
            "/api/reports/history",
            query_string={"query": "No Clear Finding", "page_size": 100},
        )
        self.assertEqual(diagnosis_query_res.status_code, 200, diagnosis_query_res.get_data(as_text=True))
        diagnosis_ids = {item["scan_id"] for item in diagnosis_query_res.get_json()["items"]}
        self.assertEqual(diagnosis_ids, {own_scan_with_report})

        patient_query_res = self.client.get(
            "/api/reports/history",
            query_string={"query": "History Patient", "page_size": 100},
        )
        self.assertEqual(patient_query_res.status_code, 200, patient_query_res.get_data(as_text=True))
        patient_ids = {item["scan_id"] for item in patient_query_res.get_json()["items"]}
        self.assertEqual(patient_ids, {own_scan_with_report, own_scan_without_report})

        patient_filter_res = self.client.get(
            "/api/reports/history",
            query_string={"patient_id": own_patient_id, "page_size": 100},
        )
        self.assertEqual(patient_filter_res.status_code, 200, patient_filter_res.get_data(as_text=True))
        patient_filter_ids = {item["scan_id"] for item in patient_filter_res.get_json()["items"]}
        self.assertEqual(patient_filter_ids, {own_scan_with_report, own_scan_without_report})

    def test_report_history_rejects_invalid_status_and_patient_id(self):
        status_res = self.client.get("/api/reports/history", query_string={"status": "invalid"})
        self.assertEqual(status_res.status_code, 400, status_res.get_data(as_text=True))
        self.assertIn("status must be", status_res.get_data(as_text=True))

        patient_res = self.client.get("/api/reports/history", query_string={"patient_id": "abc"})
        self.assertEqual(patient_res.status_code, 400, patient_res.get_data(as_text=True))
        self.assertIn("patient_id must be an integer", patient_res.get_data(as_text=True))

    def test_report_summary_fields_separated_and_ai_read_only(self):
        scan_id = self._upload_scan(scan_type="ct")
        analyze_res = self.client.post(f"/api/scans/{scan_id}/analyze")
        self.assertEqual(analyze_res.status_code, 200, analyze_res.get_data(as_text=True))

        get_report = self.client.get(f"/api/reports/{scan_id}")
        self.assertEqual(get_report.status_code, 200, get_report.get_data(as_text=True))
        report_payload = get_report.get_json()["report"]
        original_ai_summary = report_payload["ai_summary_text"]
        self.assertTrue(original_ai_summary)
        self.assertEqual(report_payload["doctor_review_text"], "")
        self.assertEqual(report_payload["patient_summary_text"], "")

        update = self.client.put(
            f"/api/reports/{scan_id}",
            json={
                "ai_summary_text": "tamper attempt",
                "doctor_review_text": "Manual doctor review in English.",
                "patient_summary_text": "நோயாளிக்கான கையேடு சுருக்கம்.",
            },
        )
        self.assertEqual(update.status_code, 200, update.get_data(as_text=True))
        updated_report = update.get_json()["report"]
        self.assertEqual(updated_report["ai_summary_text"], original_ai_summary)
        self.assertEqual(updated_report["doctor_review_text"], "Manual doctor review in English.")
        self.assertEqual(updated_report["patient_summary_text"], "நோயாளிக்கான கையேடு சுருக்கம்.")
        self.assertEqual(updated_report["doctor_notes"], "Manual doctor review in English.")

        pdf_res = self.client.get(f"/api/reports/{scan_id}/pdf", buffered=True)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, "application/pdf")
        self.assertTrue(pdf_res.get_data().startswith(b"%PDF-"))
        pdf_res.close()

    def test_legacy_report_without_patient_link_still_loads(self):
        with self.app.app_context():
            demo_user = User.query.filter_by(username="demo_doctor").first()
            scan = Scan(
                user_id=demo_user.id,
                scan_type="xray",
                original_image_path="/tmp/legacy.jpg",
                processed_image_path="/tmp/legacy_processed.jpg",
            )
            db.session.add(scan)
            db.session.flush()
            report = Report(
                scan_id=scan.id,
                patient_name="Legacy Name",
                diagnosis="Legacy Diagnosis",
                severity="mild",
                confidence_pct=65,
            )
            db.session.add(report)
            db.session.commit()
            legacy_scan_id = scan.id

        response = self.client.get(f"/api/reports/{legacy_scan_id}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIn("report", payload)
        self.assertIsNone(payload.get("patient"))


if __name__ == "__main__":
    unittest.main()

from datetime import datetime, timezone

from extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), nullable=False, unique=True)
    patient_name = db.Column(db.String(120), nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), nullable=False, default="unknown")
    confidence_pct = db.Column(db.Integer, nullable=False, default=0)
    ai_json = db.Column(db.JSON, nullable=True)
    summary_json = db.Column(db.JSON, nullable=True)
    missing_fields = db.Column(db.JSON, nullable=True)
    doctor_notes = db.Column(db.Text, nullable=True)
    final_json = db.Column(db.JSON, nullable=True)
    ai_source = db.Column(db.String(20), nullable=False, default="mock")
    ai_warning = db.Column(db.Text, nullable=True)
    pdf_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


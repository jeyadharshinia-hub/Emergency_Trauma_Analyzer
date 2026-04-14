from datetime import datetime, timezone

from extensions import db


class ScanPatientLink(db.Model):
    __tablename__ = "scan_patient_links"

    scan_id = db.Column(db.Integer, db.ForeignKey("scans.id"), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    scan = db.relationship("Scan", back_populates="patient_link")
    patient = db.relationship("Patient", back_populates="scan_links")


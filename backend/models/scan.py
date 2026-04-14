from datetime import datetime, timezone

from extensions import db


class Scan(db.Model):
    __tablename__ = "scans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scan_type = db.Column(db.String(20), nullable=False)
    original_image_path = db.Column(db.String(255), nullable=False)
    processed_image_path = db.Column(db.String(255), nullable=False)
    analyze_status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    report = db.relationship("Report", backref="scan", uselist=False)
    patient_link = db.relationship(
        "ScanPatientLink",
        back_populates="scan",
        uselist=False,
        cascade="all, delete-orphan",
    )

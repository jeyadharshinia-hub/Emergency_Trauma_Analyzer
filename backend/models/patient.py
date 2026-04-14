from datetime import datetime, timezone

from extensions import db


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    patient_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=False, default="unknown")
    phone = db.Column(db.String(24), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship("User", backref=db.backref("patients", lazy=True))
    scan_links = db.relationship("ScanPatientLink", back_populates="patient", lazy=True)


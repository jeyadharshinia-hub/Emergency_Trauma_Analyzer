from .admin import admin_bp
from .auth import auth_bp
from .patients import patients_bp
from .report import report_bp
from .scan import scan_bp

__all__ = ["auth_bp", "scan_bp", "report_bp", "patients_bp", "admin_bp"]

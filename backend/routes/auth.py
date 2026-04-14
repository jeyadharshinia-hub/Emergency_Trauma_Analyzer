from flask import Blueprint, jsonify, request, session

from extensions import bcrypt, db
from models.user import User


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_payload(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role}


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = user.id
    return jsonify({"user": _user_payload(user)})


@auth_bp.post("/quick-login")
def quick_login():
    payload = request.get_json(silent=True) or {}
    role = str(payload.get("role") or "doctor").strip().lower()
    username = "demo_doctor" if role == "doctor" else "admin"
    if role not in {"doctor", "admin"}:
        return jsonify({"error": "Role must be doctor or admin"}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "Demo user not found"}), 500
    session["user_id"] = user.id
    return jsonify({"user": _user_payload(user)})


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return jsonify({"user": None})
    return jsonify({"user": _user_payload(user)})


def _seed_user(username: str, role: str, password: str = "demo123") -> None:
    existing = User.query.filter_by(username=username).first()
    if existing:
        if existing.role != role:
            existing.role = role
            db.session.commit()
        return

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(username=username, password_hash=hashed, role=role)
    db.session.add(user)


def seed_demo_user() -> None:
    _seed_user("demo_doctor", "doctor")
    _seed_user("admin", "admin", password="admin123")
    db.session.commit()

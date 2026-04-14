from functools import wraps

from flask import jsonify, session

from extensions import db
from models.user import User


def get_current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        return handler(*args, **kwargs)

    return wrapper


def require_role(*roles):
    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            if user.role not in roles:
                return jsonify({"error": "Access denied"}), 403
            return handler(*args, **kwargs)
        return wrapper
    return decorator

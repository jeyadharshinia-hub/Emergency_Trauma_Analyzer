import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory

# Load env before importing Config so class-level env reads are correct.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

from config import Config
from extensions import bcrypt, db
from routes import admin_bp, auth_bp, patients_bp, report_bp, scan_bp
from routes.auth import seed_demo_user


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config.from_object(Config)

    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["REPORT_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        seed_demo_user()

    register_root_routes(app)
    return app


def register_root_routes(app: Flask) -> None:
    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        if path.startswith("static/"):
            static_file = path.replace("static/", "", 1)
            return send_from_directory(app.static_folder, static_file)
        if frontend_dist.exists():
            target = frontend_dist / path
            if path and target.exists():
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")
        return jsonify(
            {
                "message": "Frontend build not found. Run `npm run build` in /frontend for production mode."
            }
        )


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)

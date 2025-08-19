from pathlib import Path
from flask import Flask, send_from_directory
import os
from dotenv import load_dotenv

from db.schema import init_db, migrate_db
from routes.boxes import bp as boxes_bp
from routes.search import bp as search_bp

from routes.main import main_bp

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

    base_dir = Path(__file__).resolve().parent
    (base_dir / "uploads").mkdir(exist_ok=True)
    (base_dir / "static").mkdir(exist_ok=True)

    # ---- add this route so url_for('favicon') works ----
    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(base_dir / "static", "favicon.ico", mimetype="image/vnd.microsoft.icon")
    # ----------------------------------------------------

    # DB + blueprints
    init_db()
    migrate_db()
    app.register_blueprint(boxes_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(main_bp)
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "8081"))
    app.run(host="0.0.0.0", port=port, debug=True)

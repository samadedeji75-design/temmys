import os
from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from config import config


migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_name=None):
    from app.models import db
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Phase 8 hardening: cap request body size globally so no upload
    # endpoint (CSV import, logo upload, or any future one) can be used
    # for a memory-exhaustion DoS via an oversized payload. setdefault so
    # it doesn't clobber a value your own config.py already sets.
    app.config.setdefault("MAX_CONTENT_LENGTH", 8 * 1024 * 1024)  # 8MB

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.admin import admin_bp
    from app.teacher import teacher_bp
    from app.portal import portal_bp
    from app.auth import auth_bp
    from app.api import api_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(portal_bp, url_prefix="/portal")
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.context_processor
    def inject_current_year():
        from datetime import datetime
        return {"current_year": datetime.utcnow().year}

    @app.context_processor
    def inject_school_config():
        """Makes {{ school_config.school_name }} etc. available in every
        template without passing it manually from every route — this is
        what lets one codebase be white-labeled per school without
        touching any HTML file."""
        from types import SimpleNamespace
        from app.models import SchoolConfig

        config = SchoolConfig.query.first()
        if config is None:
            # Fresh install, before an admin has filled in Settings yet —
            # fall back to generic placeholders instead of crashing.
            config = SimpleNamespace(
                school_name="Your School Name",
                address=None,
                logo_path=None,
                phone=None,
                email=None,
                motto=None,
                active_term=None,
                active_session=None,
            )
        return {"school_config": config}

    @app.route("/")
    def index():
        # No public landing page yet — send visitors to the admin login.
        return redirect(url_for("auth.admin_login"))

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(413)
    def payload_too_large_error(error):
        return render_template("errors/generic.html"), 413

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("errors/500.html"), 500

    return app

"""Application factory for the Todo app."""
from __future__ import annotations

import click
from flask import Flask

from . import db
from .config import INSTANCE_DIR, Config
from .extensions import csrf, login_manager


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure the instance folder (holding the SQLite file) exists.
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    # Bind extensions to this app instance.
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import models so the login user loader is registered, and
    # register blueprints.
    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .todos import bp as todos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(todos_bp)

    with app.app_context():
        db.create_all()

    _register_cli(app)
    _register_error_handlers(app)

    # Make the current date available to all templates (for overdue styling).
    from datetime import date

    @app.context_processor
    def inject_globals():
        return {"today": date.today()}

    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Create database tables."""
        db.create_all()
        click.echo("Initialized the database.")


def _register_error_handlers(app: Flask) -> None:
    from flask import render_template

    @app.errorhandler(404)
    def not_found(error):  # pragma: no cover - trivial
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(error):  # pragma: no cover - defensive; no route raises 403
        return render_template("errors/404.html"), 403

"""Flask extension instances.

These are created unbound and attached to the app inside the application
factory via ``init_app`` so a single set of objects can be reused across
multiple app instances (tests, CLI, etc.).
"""
from __future__ import annotations

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models (SQLAlchemy 2.0 style)."""


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

# Where anonymous users are redirected when a view requires login.
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access that page."
login_manager.login_message_category = "info"

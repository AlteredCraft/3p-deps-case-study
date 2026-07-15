"""Authentication routes: register, login, logout."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from .extensions import db
from .forms import LoginForm, RegistrationForm
from .models import User

bp = Blueprint("auth", __name__)


def _is_safe_redirect(target: str | None) -> bool:
    """Only allow same-site relative redirects (prevents open-redirect)."""
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("todos.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.strip(), email=form.email.data.strip().lower())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome! Your account has been created.", "success")
        return redirect(url_for("todos.index"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("todos.index"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        user = db.session.scalar(
            db.select(User).where(
                (func.lower(User.username) == identifier.lower())
                | (func.lower(User.email) == identifier.lower())
            )
        )
        if user is None or not user.check_password(form.password.data):
            # Deliberately generic so we don't reveal which field was wrong.
            flash("Invalid username or password. Please try again.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        flash(f"Welcome back, {user.username}!", "success")

        next_page = request.args.get("next")
        if _is_safe_redirect(next_page):
            return redirect(next_page)
        return redirect(url_for("todos.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

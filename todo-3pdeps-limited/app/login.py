"""Purpose-built session authentication (replaces Flask-Login).

The logged-in user's id lives in Flask's (signed) session cookie; an optional
"remember me" cookie — the id plus an HMAC-SHA512 signature derived from
``SECRET_KEY`` — restores the login after the session cookie expires. Only
the surface this app uses is implemented: ``current_user``, ``login_user`` /
``logout_user``, ``login_required``, ``UserMixin``, and a ``LoginManager``
with a ``user_loader`` and login-view redirect settings.
"""
from __future__ import annotations

import functools
import hashlib
import hmac
from datetime import timedelta

from flask import Flask, current_app, flash, g, redirect, request, session, url_for
from werkzeug.local import LocalProxy

REMEMBER_COOKIE_NAME = "remember_token"
REMEMBER_COOKIE_DURATION = timedelta(days=365)


class UserMixin:
    """Default implementations for the user-object interface."""

    @property
    def is_authenticated(self) -> bool:
        return True

    def get_id(self) -> str:
        return str(self.id)


class AnonymousUser:
    is_authenticated = False


class LoginManager:
    """Unbound extension; attach with ``init_app`` in the application factory."""

    def __init__(self) -> None:
        self.login_view: str | None = None
        self.login_message = "Please log in to access that page."
        self.login_message_category = "message"
        self._user_loader = None

    def user_loader(self, callback):
        self._user_loader = callback
        return callback

    def init_app(self, app: Flask) -> None:
        app.login_manager = self
        app.context_processor(lambda: {"current_user": current_user})
        app.after_request(_apply_remember_cookie)


# ---- current user ------------------------------------------------------------

def _get_user():
    if "_login_user" not in g:
        user = None
        user_id = session.get("_user_id")
        if user_id is None:
            user_id = _decode_remember_cookie()
        loader = current_app.login_manager._user_loader
        if user_id is not None and loader is not None:
            user = loader(user_id)
        g._login_user = user if user is not None else AnonymousUser()
    return g._login_user


current_user = LocalProxy(_get_user)


def login_user(user, remember: bool = False) -> None:
    session["_user_id"] = user.get_id()
    g._login_user = user
    if remember:
        g._remember_cookie = "set"


def logout_user() -> None:
    session.pop("_user_id", None)
    g._login_user = AnonymousUser()
    if REMEMBER_COOKIE_NAME in request.cookies:
        g._remember_cookie = "clear"


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            manager = current_app.login_manager
            flash(manager.login_message, manager.login_message_category)
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for(manager.login_view, next=next_url))
        return view(*args, **kwargs)

    return wrapped


# ---- remember-me cookie --------------------------------------------------------

def _cookie_digest(payload: str) -> str:
    key = current_app.secret_key
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha512).hexdigest()


def _decode_remember_cookie() -> str | None:
    cookie = request.cookies.get(REMEMBER_COOKIE_NAME, "")
    payload, _, digest = cookie.rpartition("|")
    if payload and hmac.compare_digest(_cookie_digest(payload), digest):
        return payload
    return None


def _apply_remember_cookie(response):
    action = g.get("_remember_cookie")
    if action == "set":
        user_id = session["_user_id"]
        config = current_app.config
        response.set_cookie(
            REMEMBER_COOKIE_NAME,
            f"{user_id}|{_cookie_digest(user_id)}",
            max_age=REMEMBER_COOKIE_DURATION,
            httponly=config.get("REMEMBER_COOKIE_HTTPONLY", True),
            secure=config.get("REMEMBER_COOKIE_SECURE", False),
            samesite=config.get("REMEMBER_COOKIE_SAMESITE"),
        )
    elif action == "clear":
        response.delete_cookie(REMEMBER_COOKIE_NAME)
    return response

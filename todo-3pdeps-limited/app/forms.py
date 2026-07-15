"""Form definitions and validation (WTForms + first-party Flask glue)."""
from __future__ import annotations

import re

from flask import request
from markupsafe import Markup
from wtforms import (
    BooleanField,
    DateField,
    Form,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from .csrf import generate_csrf
from .models import PRIORITIES, email_exists, username_exists


class BaseForm(Form):
    """WTForms ``Form`` + the Flask conveniences we used from FlaskForm.

    Binds POST data from the current request, and renders the session CSRF
    token as the hidden input the templates (and tests) expect. Token
    *validation* is global — see :mod:`app.csrf`.
    """

    def __init__(self, obj=None, **kwargs) -> None:
        formdata = request.form if request.method == "POST" else None
        super().__init__(formdata=formdata, obj=obj, **kwargs)

    def validate_on_submit(self) -> bool:
        return request.method == "POST" and self.validate()

    @property
    def csrf_token(self) -> Markup:
        return Markup(
            f'<input id="csrf_token" name="csrf_token" type="hidden" value="{generate_csrf()}">'
        )


# Precise, format-only email validation (replaces email-validator, which
# shipped an IDNA + DNS stack for deliverability checks we never used).
# ASCII dot-atom local part, dot-separated alphanumeric/hyphen domain labels.
_EMAIL_ATOM = r"[A-Za-z0-9!#$%&'*+\-/=?^_`{|}~]+"
_EMAIL_LOCAL_RE = re.compile(rf"^{_EMAIL_ATOM}(\.{_EMAIL_ATOM})*$")
_EMAIL_LABEL_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def is_valid_email(value: str) -> bool:
    local, sep, domain = value.rpartition("@")
    if not sep or not local or not domain:
        return False
    if len(local) > 64 or len(domain) > 253:
        return False
    if not _EMAIL_LOCAL_RE.match(local):
        return False
    labels = domain.split(".")
    # Like email-validator, require a dot (a TLD) after the @-sign.
    if len(labels) < 2:
        return False
    return all(_EMAIL_LABEL_RE.match(label) for label in labels)


class EmailFormat:
    """WTForms-style validator wrapping :func:`is_valid_email`."""

    def __init__(self, message: str = "Invalid email address.") -> None:
        self.message = message

    def __call__(self, form: Form, field: StringField) -> None:
        if not is_valid_email(field.data or ""):
            raise ValidationError(self.message)


class RegistrationForm(BaseForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Use only letters, numbers, and _ . - characters.",
            ),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), EmailFormat(), Length(max=120)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")

    def validate_username(self, field: StringField) -> None:
        if username_exists(field.data):
            raise ValidationError("That username is already taken.")

    def validate_email(self, field: StringField) -> None:
        if email_exists(field.data):
            raise ValidationError("An account with that email already exists.")


class LoginForm(BaseForm):
    username = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class TaskForm(BaseForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    category = StringField(
        "Category",
        validators=[Optional(), Length(max=60)],
        description="Optional. e.g. Work, Home, Errands",
    )
    priority = SelectField(
        "Priority",
        choices=[(p, p.capitalize()) for p in PRIORITIES],
        default="medium",
        validators=[DataRequired()],
    )
    due_date = DateField("Due date", validators=[Optional()])
    submit = SubmitField("Save task")

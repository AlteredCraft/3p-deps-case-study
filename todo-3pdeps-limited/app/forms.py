"""Form definitions and validation (Flask-WTF / WTForms)."""
from __future__ import annotations

from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (
    BooleanField,
    DateField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from .extensions import db
from .models import PRIORITIES, User


class RegistrationForm(FlaskForm):
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
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")

    def validate_username(self, field: StringField) -> None:
        existing = db.session.scalar(
            db.select(User).where(func.lower(User.username) == field.data.lower())
        )
        if existing:
            raise ValidationError("That username is already taken.")

    def validate_email(self, field: StringField) -> None:
        existing = db.session.scalar(
            db.select(User).where(func.lower(User.email) == field.data.lower())
        )
        if existing:
            raise ValidationError("An account with that email already exists.")


class LoginForm(FlaskForm):
    username = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class TaskForm(FlaskForm):
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

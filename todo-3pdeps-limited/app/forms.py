"""Form definitions and validation (first-party — see app/formlib.py)."""
from __future__ import annotations

from .formlib import (
    BooleanField,
    DataRequired,
    DateField,
    EmailFormat,
    EqualTo,
    Form,
    Length,
    Optional,
    PasswordField,
    Regexp,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    ValidationError,
)
from .models import PRIORITIES, email_exists, username_exists


class RegistrationForm(Form):
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


class LoginForm(Form):
    username = StringField("Username or email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class TaskForm(Form):
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

"""A purpose-built micro form library (replaces WTForms for this app's needs).

Implements only what the templates and routes actually use: seven field
types, the validators the forms declare, request/obj binding, per-field
error lists, inline ``validate_<field>`` hooks, and HTML rendering that
matches the markup WTForms produced (sorted attributes, ``<label for>``,
selected options, checkbox semantics). Error messages reproduce the
WTForms defaults the test suite pins.
"""
from __future__ import annotations

import copy
import re
from datetime import date

from flask import current_app, request
from markupsafe import Markup, escape

from .csrf import generate_csrf


class ValidationError(Exception):
    """Raised by a validator to reject a field's value."""


class _SkipField(Exception):
    """Raised by Optional to accept an empty field, skipping later validators."""


def html_params(**kwargs) -> str:
    """Render sorted HTML attributes; True renders as a bare attribute."""
    parts = []
    for key, value in sorted(kwargs.items()):
        if value is True:
            parts.append(key)
        elif value is not False and value is not None:
            parts.append(f'{key}="{escape(value)}"')
    return " ".join(parts)


# ---- validators ---------------------------------------------------------------

class DataRequired:
    def __init__(self, message: str = "This field is required.") -> None:
        self.message = message

    def __call__(self, form, field) -> None:
        if not field.data or (isinstance(field.data, str) and not field.data.strip()):
            raise ValidationError(self.message)


class Optional:
    """Accept an empty submitted value, skipping the remaining validators."""

    def __call__(self, form, field) -> None:
        if field.raw is None or (isinstance(field.raw, str) and not field.raw.strip()):
            raise _SkipField()


class Length:
    def __init__(self, min: int = -1, max: int = -1, message: str | None = None) -> None:
        self.min, self.max, self.message = min, max, message

    def __call__(self, form, field) -> None:
        length = len(field.data or "")
        if (self.min != -1 and length < self.min) or (self.max != -1 and length > self.max):
            if self.message:
                message = self.message
            elif self.min != -1 and self.max != -1:
                message = f"Field must be between {self.min} and {self.max} characters long."
            elif self.max != -1:
                message = f"Field cannot be longer than {self.max} characters."
            else:
                message = f"Field must be at least {self.min} characters long."
            raise ValidationError(message)


class Regexp:
    def __init__(self, pattern: str, message: str | None = None) -> None:
        self.regex = re.compile(pattern)
        self.message = message or "Invalid input."

    def __call__(self, form, field) -> None:
        if not self.regex.match(field.data or ""):
            raise ValidationError(self.message)


class EqualTo:
    def __init__(self, fieldname: str, message: str | None = None) -> None:
        self.fieldname = fieldname
        self.message = message or f"Field must be equal to {fieldname}."

    def __call__(self, form, field) -> None:
        if field.data != getattr(form, self.fieldname).data:
            raise ValidationError(self.message)


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
    def __init__(self, message: str = "Invalid email address.") -> None:
        self.message = message

    def __call__(self, form, field) -> None:
        if not is_valid_email(field.data or ""):
            raise ValidationError(self.message)


# ---- fields --------------------------------------------------------------------

class Field:
    input_type = "text"

    def __init__(self, label: str, validators=(), default=None, description: str = ""):
        self.label_text = label
        self.validators = list(validators)
        self.default = default
        self.description = description
        self.name: str = ""
        self.data = None
        self.raw: str | None = None       # submitted string, None if absent
        self.errors: list[str] = []
        self._process_error: str | None = None

    # -- binding ---------------------------------------------------------------

    def process(self, formdata, obj) -> None:
        if obj is not None and hasattr(obj, self.name):
            self.data = getattr(obj, self.name)
        else:
            self.data = self.default
        if formdata is not None:
            self.raw = formdata.get(self.name)
            self._process_formdata()

    def _process_formdata(self) -> None:
        # Like WTForms: an absent key leaves the obj/default value in place.
        if self.raw is not None:
            self.data = self.raw

    # -- validation --------------------------------------------------------------

    def validate(self, form) -> bool:
        self.errors = []
        try:
            if self._process_error:
                raise ValidationError(self._process_error)
            self._pre_validate()
            for validator in self.validators:
                validator(form, self)
            inline = getattr(form, f"validate_{self.name}", None)
            if inline is not None:
                inline(self)
        except _SkipField:
            self.errors = []
        except ValidationError as exc:
            self.errors.append(str(exc))
        return not self.errors

    def _pre_validate(self) -> None:
        pass

    # -- rendering -----------------------------------------------------------------

    @property
    def label(self) -> Markup:
        return Markup(f'<label for="{self.name}">{escape(self.label_text)}</label>')

    def _value(self) -> str:
        if self.raw is not None:
            return self.raw
        return "" if self.data is None else str(self.data)

    def _constraint_attrs(self) -> dict:
        """HTML5 constraint attributes implied by the validators."""
        attrs: dict = {}
        for validator in self.validators:
            if isinstance(validator, DataRequired):
                attrs["required"] = True
            elif isinstance(validator, Length):
                if validator.min != -1:
                    attrs["minlength"] = validator.min
                if validator.max != -1:
                    attrs["maxlength"] = validator.max
        return attrs

    def __call__(self, **kwargs) -> Markup:
        attrs = {"id": self.name, "name": self.name, "type": self.input_type}
        attrs.update(self._constraint_attrs())
        attrs.update(kwargs)
        attrs.setdefault("value", self._value())
        return Markup(f"<input {html_params(**attrs)}>")


class StringField(Field):
    pass


class PasswordField(StringField):
    input_type = "password"

    def _value(self) -> str:
        return ""  # never re-render a submitted password


class TextAreaField(StringField):
    def __call__(self, **kwargs) -> Markup:
        attrs = {"id": self.name, "name": self.name}
        attrs.update(self._constraint_attrs())
        attrs.update(kwargs)
        # The leading newline protects a value that itself starts with one
        # (browsers ignore the first newline after <textarea>).
        return Markup(
            f"<textarea {html_params(**attrs)}>\r\n{escape(self._value())}</textarea>"
        )


class BooleanField(Field):
    input_type = "checkbox"

    def __init__(self, label: str, validators=(), default=False, **kwargs):
        super().__init__(label, validators, default, **kwargs)

    def _process_formdata(self) -> None:
        # Checkbox semantics: absent from the POST means unchecked.
        self.data = self.raw is not None

    def __call__(self, **kwargs) -> Markup:
        attrs = {"id": self.name, "name": self.name, "type": self.input_type, "value": "y"}
        if self.data:
            attrs["checked"] = True
        attrs.update(kwargs)
        return Markup(f"<input {html_params(**attrs)}>")


class DateField(Field):
    def _process_formdata(self) -> None:
        self._process_error = None
        if self.raw is None:
            return
        if not self.raw.strip():
            self.data = None
            return
        try:
            self.data = date.fromisoformat(self.raw)
        except ValueError:
            self.data = None
            self._process_error = "Not a valid date value."

    def _value(self) -> str:
        if self.raw is not None:
            return self.raw
        return self.data.isoformat() if self.data else ""


class SelectField(Field):
    def __init__(self, label: str, choices=(), validators=(), default=None, **kwargs):
        super().__init__(label, validators, default, **kwargs)
        self.choices = list(choices)

    def _pre_validate(self) -> None:
        if self.data not in {value for value, _ in self.choices}:
            raise ValidationError("Not a valid choice.")

    def __call__(self, **kwargs) -> Markup:
        attrs = {"id": self.name, "name": self.name}
        attrs.update(self._constraint_attrs())
        attrs.update(kwargs)
        options = "".join(
            f'<option {html_params(selected=(value == self.data), value=value)}>'
            f"{escape(text)}</option>"
            for value, text in self.choices
        )
        return Markup(f"<select {html_params(**attrs)}>{options}</select>")


class SubmitField(Field):
    input_type = "submit"

    def _value(self) -> str:
        return self.label_text

    def validate(self, form) -> bool:
        return True


# ---- form base -------------------------------------------------------------------

class Form:
    """Declarative form: fields as class attributes, bound per instance.

    Binds POST data from the current request, prefills from ``obj`` on GET,
    and renders the session CSRF token as the hidden input the templates
    expect. Token *validation* is global — see :mod:`app.csrf`.
    """

    def __init__(self, obj=None) -> None:
        self._fields: list[Field] = []
        for klass in reversed(type(self).__mro__):
            for name, proto in vars(klass).items():
                if isinstance(proto, Field):
                    field = copy.deepcopy(proto)
                    field.name = name
                    setattr(self, name, field)
                    self._fields.append(field)
        formdata = request.form if request.method == "POST" else None
        for field in self._fields:
            field.process(formdata, obj)

    def validate(self) -> bool:
        return all([field.validate(self) for field in self._fields])

    def validate_on_submit(self) -> bool:
        return request.method == "POST" and self.validate()

    @property
    def csrf_token(self) -> Markup:
        if not current_app.config.get("CSRF_ENABLED", True):
            return Markup("")
        return Markup(
            f'<input id="csrf_token" name="csrf_token" type="hidden" value="{generate_csrf()}">'
        )

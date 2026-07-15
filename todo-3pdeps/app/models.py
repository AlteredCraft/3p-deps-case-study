"""Database models."""
from __future__ import annotations

from datetime import date, datetime, timezone

from flask_login import UserMixin
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

# Allowed priority values, ordered from most to least urgent.
PRIORITIES = ("high", "medium", "low")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Task.created_at.desc()",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.username!r}>"


class Task(db.Model):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str] = mapped_column(String(60), default="", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium", index=True)
    due_date: Mapped[date | None] = mapped_column(default=None)
    completed: Mapped[bool] = mapped_column(default=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="tasks")

    def toggle(self) -> None:
        """Flip completion state, tracking when it was completed."""
        self.completed = not self.completed
        self.completed_at = _utcnow() if self.completed else None

    @property
    def is_overdue(self) -> bool:
        return (
            not self.completed
            and self.due_date is not None
            and self.due_date < date.today()
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task {self.id} {self.title!r} completed={self.completed}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    # SQLAlchemy 2.0 style primary-key lookup.
    return db.session.get(User, int(user_id))

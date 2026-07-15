"""Data models and the queries that back them (stdlib sqlite3, no ORM)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .extensions import login_manager
from .login import UserMixin

# Allowed priority values, ordered from most to least urgent.
PRIORITIES = ("high", "medium", "low")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _utcnow() -> str:
    """Current UTC time, in the ISO text form stored in DATETIME columns."""
    return datetime.now(timezone.utc).isoformat(sep=" ")


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """Run a write statement and commit it."""
    con = get_db()
    cur = con.execute(sql, params)
    con.commit()
    return cur


@dataclass
class User(UserMixin):
    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            created_at=_parse_dt(row["created_at"]),
        )

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@dataclass
class Task:
    id: int
    user_id: int
    title: str
    notes: str
    category: str
    priority: str
    due_date: date | None
    completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            notes=row["notes"],
            category=row["category"],
            priority=row["priority"],
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            completed=bool(row["completed"]),
            completed_at=_parse_dt(row["completed_at"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    @property
    def is_overdue(self) -> bool:
        return (
            not self.completed
            and self.due_date is not None
            and self.due_date < date.today()
        )


# ---- user queries ------------------------------------------------------------

def get_user(user_id: int) -> User | None:
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User.from_row(row) if row else None


def find_user_by_login(identifier: str) -> User | None:
    """Look up a user by username or email, case-insensitively."""
    row = get_db().execute(
        "SELECT * FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
        (identifier, identifier),
    ).fetchone()
    return User.from_row(row) if row else None


def username_exists(username: str) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM users WHERE lower(username) = lower(?)", (username,)
    ).fetchone()
    return row is not None


def email_exists(email: str) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM users WHERE lower(email) = lower(?)", (email,)
    ).fetchone()
    return row is not None


def create_user(username: str, email: str, password: str) -> User:
    cur = _execute(
        "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (username, email, generate_password_hash(password), _utcnow()),
    )
    return get_user(cur.lastrowid)


# ---- task queries ------------------------------------------------------------

def get_task(task_id: int) -> Task | None:
    row = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row) if row else None


def create_task(
    user_id: int,
    *,
    title: str,
    notes: str,
    category: str,
    priority: str,
    due_date: date | None,
) -> None:
    now = _utcnow()
    _execute(
        "INSERT INTO tasks (user_id, title, notes, category, priority, due_date,"
        " completed, completed_at, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)",
        (user_id, title, notes, category, priority,
         due_date.isoformat() if due_date else None, now, now),
    )


def update_task(
    task_id: int,
    *,
    title: str,
    notes: str,
    category: str,
    priority: str,
    due_date: date | None,
) -> None:
    _execute(
        "UPDATE tasks SET title = ?, notes = ?, category = ?, priority = ?,"
        " due_date = ?, updated_at = ? WHERE id = ?",
        (title, notes, category, priority,
         due_date.isoformat() if due_date else None, _utcnow(), task_id),
    )


def toggle_task(task: Task) -> None:
    """Flip completion state, tracking when it was completed."""
    now_done = not task.completed
    _execute(
        "UPDATE tasks SET completed = ?, completed_at = ?, updated_at = ? WHERE id = ?",
        (int(now_done), _utcnow() if now_done else None, _utcnow(), task.id),
    )


def delete_task(task_id: int) -> None:
    _execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def clear_completed(user_id: int) -> int:
    """Delete the user's completed tasks; returns how many were removed."""
    return _execute(
        "DELETE FROM tasks WHERE user_id = ? AND completed = 1", (user_id,)
    ).rowcount


def priority_ordering() -> str:
    """SQL CASE so 'high' < 'medium' < 'low' sort correctly (sorting stays in SQL)."""
    whens = " ".join(f"WHEN '{p}' THEN {rank}" for p, rank in PRIORITY_RANK.items())
    return f"CASE priority {whens} ELSE 1 END"


def list_tasks(
    user_id: int,
    *,
    status: str = "all",
    category: str = "",
    priority: str = "",
    search: str = "",
    sort: str = "created",
) -> list[Task]:
    sql = "SELECT * FROM tasks WHERE user_id = ?"
    params: list = [user_id]

    if status == "active":
        sql += " AND completed = 0"
    elif status == "completed":
        sql += " AND completed = 1"
    if category:
        sql += " AND category = ?"
        params.append(category)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if search:
        pattern = f"%{search.lower()}%"
        sql += " AND (lower(title) LIKE ? OR lower(notes) LIKE ?)"
        params += [pattern, pattern]

    # Always surface incomplete work first, then apply the chosen sort.
    orderings = {
        "created": "created_at DESC",
        "due": "(due_date IS NULL) ASC, due_date ASC",  # NULL due dates sort last
        "priority": f"{priority_ordering()} ASC",
        "title": "lower(title) ASC",
    }
    sql += f" ORDER BY completed ASC, {orderings[sort]}"

    return [Task.from_row(row) for row in get_db().execute(sql, params)]


def distinct_categories(user_id: int) -> list[str]:
    rows = get_db().execute(
        "SELECT DISTINCT category FROM tasks WHERE user_id = ? AND category != ''"
        " ORDER BY category",
        (user_id,),
    )
    return [row["category"] for row in rows]


def task_stats(user_id: int) -> dict[str, int]:
    row = get_db().execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(completed = 0), 0) AS remaining"
        " FROM tasks WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return {
        "total": row["total"],
        "remaining": row["remaining"],
        "done": row["total"] - row["remaining"],
    }


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return get_user(int(user_id))

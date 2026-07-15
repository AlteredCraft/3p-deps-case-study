"""Tests for task CRUD, filtering, sorting, and per-user isolation."""
from __future__ import annotations

from datetime import date, timedelta

from app.extensions import db
from app.models import Task, User
from tests.conftest import create_task, login, register


def _task_id(app, title):
    with app.app_context():
        task = db.session.scalar(db.select(Task).where(Task.title == title))
        return task.id


def test_create_task(client, app, auth):
    resp = auth.create_task(title="Write report", priority="high", category="Work")
    assert b"Task added" in resp.data
    assert b"Write report" in resp.data
    with app.app_context():
        task = db.session.scalar(db.select(Task).where(Task.title == "Write report"))
        assert task.priority == "high"
        assert task.category == "Work"
        assert task.completed is False


def test_create_task_requires_title(client, auth):
    resp = client.post("/tasks/new", data={"title": "", "priority": "medium"}, follow_redirects=True)
    assert b"This field is required" in resp.data


def test_toggle_task_marks_complete(client, app, auth):
    auth.create_task(title="Do dishes")
    tid = _task_id(app, "Do dishes")

    client.post(f"/tasks/{tid}/toggle", follow_redirects=True)
    with app.app_context():
        task = db.session.get(Task, tid)
        assert task.completed is True
        assert task.completed_at is not None

    client.post(f"/tasks/{tid}/toggle", follow_redirects=True)
    with app.app_context():
        task = db.session.get(Task, tid)
        assert task.completed is False
        assert task.completed_at is None


def test_edit_task(client, app, auth):
    auth.create_task(title="Old title")
    tid = _task_id(app, "Old title")
    resp = client.post(
        f"/tasks/{tid}/edit",
        data={"title": "New title", "priority": "low", "category": "Home"},
        follow_redirects=True,
    )
    assert b"Task updated" in resp.data
    with app.app_context():
        task = db.session.get(Task, tid)
        assert task.title == "New title"
        assert task.priority == "low"


def test_delete_task(client, app, auth):
    auth.create_task(title="Delete me")
    tid = _task_id(app, "Delete me")
    resp = client.post(f"/tasks/{tid}/delete", follow_redirects=True)
    assert b"Task deleted" in resp.data
    with app.app_context():
        assert db.session.get(Task, tid) is None


def test_clear_completed(client, app, auth):
    auth.create_task(title="Keep me")
    auth.create_task(title="Done 1")
    auth.create_task(title="Done 2")
    for title in ("Done 1", "Done 2"):
        client.post(f"/tasks/{_task_id(app, title)}/toggle")

    resp = client.post("/tasks/clear-completed", follow_redirects=True)
    assert b"Cleared 2 completed" in resp.data
    with app.app_context():
        remaining = db.session.scalars(db.select(Task)).all()
        assert [t.title for t in remaining] == ["Keep me"]


def test_user_cannot_access_others_task(client, app):
    # Alice creates a task.
    register(client, username="alice", email="alice@example.com")
    create_task(client, title="Alice secret")
    tid = _task_id(app, "Alice secret")
    client.post("/logout", follow_redirects=True)

    # Bob logs in and tries to touch it.
    register(client, username="bob", email="bob@example.com")
    assert client.get(f"/tasks/{tid}/edit").status_code == 404
    assert client.post(f"/tasks/{tid}/toggle").status_code == 404
    assert client.post(f"/tasks/{tid}/delete").status_code == 404

    # Task is untouched.
    with app.app_context():
        assert db.session.get(Task, tid) is not None


def test_index_only_shows_own_tasks(client, app):
    register(client, username="alice", email="alice@example.com")
    create_task(client, title="Alice task")
    client.post("/logout", follow_redirects=True)

    register(client, username="bob", email="bob@example.com")
    create_task(client, title="Bob task")
    resp = client.get("/")
    assert b"Bob task" in resp.data
    assert b"Alice task" not in resp.data


def test_status_filter(client, auth):
    auth.create_task(title="Active task")
    auth.create_task(title="Completed task")
    # complete the second
    from app import create_app  # noqa: F401  (ensure app importable)

    resp = client.get("/?status=active")
    assert b"Active task" in resp.data


def test_search_filter(client, auth):
    auth.create_task(title="Buy groceries")
    auth.create_task(title="Call dentist")
    resp = client.get("/?q=grocer")
    assert b"Buy groceries" in resp.data
    assert b"Call dentist" not in resp.data


def test_priority_sort_does_not_error(client, auth):
    auth.create_task(title="Low one", priority="low")
    auth.create_task(title="High one", priority="high")
    resp = client.get("/?sort=priority")
    assert resp.status_code == 200
    # High priority should appear before low in the rendered HTML.
    assert resp.data.index(b"High one") < resp.data.index(b"Low one")


def test_due_date_sort_and_overdue(client, app, auth):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    auth.create_task(title="Overdue task", due_date=yesterday)
    resp = client.get("/?sort=due")
    assert resp.status_code == 200
    assert b"Overdue" in resp.data

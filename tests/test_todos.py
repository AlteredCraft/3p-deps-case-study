"""Task CRUD, filtering, sorting, and per-user isolation — black-box.

Drives the app over HTTP; persisted-state checks use the stdlib sqlite3 helper.
These pin the behavior currently provided by SQLAlchemy and WTForms so a
dependency swap must preserve it.
"""
from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import create_task, db_query, logout, register, task_id


# ---- create -----------------------------------------------------------------

def test_create_task_renders_on_index(client, auth):
    resp = auth.create_task(title="Write report", priority="high", category="Work")
    assert b"Task added" in resp.data
    assert b'task-title">Write report' in resp.data
    assert b"badge-high" in resp.data
    assert b"Work" in resp.data


def test_create_requires_title(client, auth):
    resp = client.post("/tasks/new", data={"title": "", "priority": "medium"},
                       follow_redirects=True)
    assert b"This field is required" in resp.data


def test_create_rejects_invalid_priority(client, auth):
    resp = client.post("/tasks/new", data={"title": "X", "priority": "urgent"},
                       follow_redirects=True)
    assert b"Not a valid choice" in resp.data


def test_create_rejects_invalid_due_date(client, auth):
    resp = client.post(
        "/tasks/new",
        data={"title": "X", "priority": "low", "due_date": "not-a-date"},
        follow_redirects=True,
    )
    assert b"Not a valid date" in resp.data


# ---- toggle / edit / delete -------------------------------------------------

def test_toggle_marks_done_and_back(client, auth, db_path):
    auth.create_task(title="Do dishes")
    tid = task_id(db_path, "Do dishes")

    client.post(f"/tasks/{tid}/toggle", follow_redirects=True)
    assert b"is-done" in client.get("/").data          # HTTP-observable
    row = db_query(db_path, "SELECT completed, completed_at FROM tasks WHERE id = ?", (tid,))[0]
    assert row["completed"] == 1
    assert row["completed_at"] is not None              # not HTTP-observable

    client.post(f"/tasks/{tid}/toggle", follow_redirects=True)
    row = db_query(db_path, "SELECT completed, completed_at FROM tasks WHERE id = ?", (tid,))[0]
    assert row["completed"] == 0
    assert row["completed_at"] is None


def test_edit_updates_task(client, auth, db_path):
    auth.create_task(title="Old title", priority="high")
    tid = task_id(db_path, "Old title")
    resp = client.post(
        f"/tasks/{tid}/edit",
        data={"title": "New title", "priority": "low", "category": "Home"},
        follow_redirects=True,
    )
    assert b"Task updated" in resp.data
    assert b'task-title">New title' in resp.data
    assert b"Old title" not in resp.data
    assert b"badge-low" in resp.data


def test_delete_removes_task(client, auth, db_path):
    auth.create_task(title="Delete me")
    tid = task_id(db_path, "Delete me")
    resp = client.post(f"/tasks/{tid}/delete", follow_redirects=True)
    assert b"Task deleted" in resp.data
    assert b"Delete me" not in resp.data
    assert db_query(db_path, "SELECT COUNT(*) c FROM tasks WHERE id = ?", (tid,))[0]["c"] == 0


def test_clear_completed(client, auth, db_path):
    for t in ("Keep me", "Done 1", "Done 2"):
        auth.create_task(title=t)
    for t in ("Done 1", "Done 2"):
        client.post(f"/tasks/{task_id(db_path, t)}/toggle")

    resp = client.post("/tasks/clear-completed", follow_redirects=True)
    assert b"Cleared 2 completed" in resp.data
    titles = [r["title"] for r in db_query(db_path, "SELECT title FROM tasks")]
    assert titles == ["Keep me"]


# ---- per-user isolation (authorization) -------------------------------------

def test_user_cannot_touch_others_task(client, db_path):
    register(client, username="alice", email="alice@example.com")
    create_task(client, title="Alice secret")
    tid = task_id(db_path, "Alice secret")
    logout(client)

    register(client, username="bob", email="bob@example.com")
    assert client.get(f"/tasks/{tid}/edit").status_code == 404
    assert client.post(f"/tasks/{tid}/toggle").status_code == 404
    assert client.post(f"/tasks/{tid}/delete").status_code == 404
    # Untouched.
    assert db_query(db_path, "SELECT COUNT(*) c FROM tasks WHERE id = ?", (tid,))[0]["c"] == 1


def test_index_shows_only_own_tasks(client):
    register(client, username="alice", email="alice@example.com")
    create_task(client, title="Alice task")
    logout(client)
    register(client, username="bob", email="bob@example.com")
    create_task(client, title="Bob task")

    page = client.get("/").data
    assert b"Bob task" in page
    assert b"Alice task" not in page


# ---- filtering --------------------------------------------------------------

def test_status_filter_hides_the_other_set(client, auth, db_path):
    auth.create_task(title="Active one")
    auth.create_task(title="Completed one")
    client.post(f"/tasks/{task_id(db_path, 'Completed one')}/toggle")

    active = client.get("/?status=active").data
    assert b"Active one" in active
    assert b"Completed one" not in active

    completed = client.get("/?status=completed").data
    assert b"Completed one" in completed
    assert b"Active one" not in completed


def test_category_filter(client, auth):
    auth.create_task(title="Work thing", category="Work")
    auth.create_task(title="Home thing", category="Home")
    page = client.get("/?category=Work").data
    assert b"Work thing" in page
    assert b"Home thing" not in page


def test_priority_filter(client, auth):
    auth.create_task(title="Urgent thing", priority="high")
    auth.create_task(title="Whenever thing", priority="low")
    page = client.get("/?priority=high").data
    assert b"Urgent thing" in page
    assert b"Whenever thing" not in page


def test_search_matches_title(client, auth):
    auth.create_task(title="Buy groceries")
    auth.create_task(title="Call dentist")
    page = client.get("/?q=grocer").data
    assert b"Buy groceries" in page
    assert b"Call dentist" not in page


def test_search_matches_notes(client, auth):
    auth.create_task(title="Task one", notes="remember the milk")
    auth.create_task(title="Task two", notes="nothing here")
    page = client.get("/?q=milk").data
    assert b"Task one" in page
    assert b"Task two" not in page


# ---- sorting ----------------------------------------------------------------

def test_priority_sort_orders_high_first(client, auth):
    auth.create_task(title="Low one", priority="low")
    auth.create_task(title="High one", priority="high")
    page = client.get("/?sort=priority").data
    assert page.index(b"High one") < page.index(b"Low one")


def test_due_sort_and_overdue_badge(client, auth):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    auth.create_task(title="Overdue task", due_date=yesterday)
    page = client.get("/?sort=due").data
    assert b"Overdue" in page


def test_title_sort_is_alphabetical(client, auth):
    auth.create_task(title="Zebra task")
    auth.create_task(title="Apple task")
    page = client.get("/?sort=title").data
    assert page.index(b"Apple task") < page.index(b"Zebra task")


def test_invalid_sort_falls_back(client, auth):
    auth.create_task(title="A task")
    resp = client.get("/?sort=bogus")
    assert resp.status_code == 200
    assert b"A task" in resp.data


# ---- edit form (GET) --------------------------------------------------------

def test_edit_form_renders_prefilled(client, auth, db_path):
    auth.create_task(title="Edit me", priority="high", category="Work")
    tid = task_id(db_path, "Edit me")
    resp = client.get(f"/tasks/{tid}/edit")
    assert resp.status_code == 200
    assert b"Edit task" in resp.data
    assert b'value="Edit me"' in resp.data  # form prefilled with current values

"""Todo (task) routes: list, create, edit, toggle, delete."""
from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import case, func

from .extensions import db
from .forms import TaskForm
from .models import PRIORITY_RANK, Task

bp = Blueprint("todos", __name__)

# Sort options exposed in the UI -> ORDER BY expression builder.
SORT_OPTIONS = {
    "created": "Newest",
    "due": "Due date",
    "priority": "Priority",
    "title": "Title (A–Z)",
}


def _get_owned_task_or_404(task_id: int) -> Task:
    """Fetch a task, ensuring it belongs to the logged-in user."""
    task = db.session.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        abort(404)
    return task


def _priority_ordering():
    """SQL CASE so 'high' < 'medium' < 'low' sort correctly."""
    return case(PRIORITY_RANK, value=Task.priority, else_=1)


@bp.route("/")
@login_required
def index():
    status = request.args.get("status", "all")
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "created")
    if sort not in SORT_OPTIONS:
        sort = "created"

    query = db.select(Task).where(Task.user_id == current_user.id)

    if status == "active":
        query = query.where(Task.completed.is_(False))
    elif status == "completed":
        query = query.where(Task.completed.is_(True))

    if category:
        query = query.where(Task.category == category)
    if priority:
        query = query.where(Task.priority == priority)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            Task.title.ilike(pattern) | Task.notes.ilike(pattern)
        )

    # Always surface incomplete work first, then apply the chosen sort.
    order = [Task.completed.asc()]
    if sort == "due":
        # NULL due dates sort last.
        order += [Task.due_date.is_(None).asc(), Task.due_date.asc()]
    elif sort == "priority":
        order += [_priority_ordering().asc()]
    elif sort == "title":
        order += [func.lower(Task.title).asc()]
    else:  # created
        order += [Task.created_at.desc()]
    query = query.order_by(*order)

    tasks = db.session.scalars(query).all()

    # Distinct categories for the filter dropdown.
    categories = db.session.scalars(
        db.select(Task.category)
        .where(Task.user_id == current_user.id, Task.category != "")
        .distinct()
        .order_by(Task.category)
    ).all()

    # Header stats.
    total = db.session.scalar(
        db.select(func.count(Task.id)).where(Task.user_id == current_user.id)
    )
    remaining = db.session.scalar(
        db.select(func.count(Task.id)).where(
            Task.user_id == current_user.id, Task.completed.is_(False)
        )
    )
    stats = {"total": total, "remaining": remaining, "done": total - remaining}

    return render_template(
        "todos/index.html",
        tasks=tasks,
        stats=stats,
        categories=categories,
        sort_options=SORT_OPTIONS,
        filters={
            "status": status,
            "category": category,
            "priority": priority,
            "q": search,
            "sort": sort,
        },
    )


@bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def create():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            user_id=current_user.id,
            title=form.title.data.strip(),
            notes=(form.notes.data or "").strip(),
            category=(form.category.data or "").strip(),
            priority=form.priority.data,
            due_date=form.due_date.data,
        )
        db.session.add(task)
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("todos.index"))

    return render_template("todos/form.html", form=form, title="New task", task=None)


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit(task_id: int):
    task = _get_owned_task_or_404(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.notes = (form.notes.data or "").strip()
        task.category = (form.category.data or "").strip()
        task.priority = form.priority.data
        task.due_date = form.due_date.data
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("todos.index"))

    return render_template("todos/form.html", form=form, title="Edit task", task=task)


@bp.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle(task_id: int):
    task = _get_owned_task_or_404(task_id)
    task.toggle()
    db.session.commit()
    return redirect(request.referrer or url_for("todos.index"))


@bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete(task_id: int):
    task = _get_owned_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(request.referrer or url_for("todos.index"))


@bp.route("/tasks/clear-completed", methods=["POST"])
@login_required
def clear_completed():
    deleted = db.session.query(Task).filter(
        Task.user_id == current_user.id, Task.completed.is_(True)
    ).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Cleared {deleted} completed task(s).", "info")
    return redirect(url_for("todos.index"))

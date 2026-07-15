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

from . import models
from .forms import TaskForm
from .models import Task

bp = Blueprint("todos", __name__)

# Sort options exposed in the UI -> ORDER BY handled in models.list_tasks.
SORT_OPTIONS = {
    "created": "Newest",
    "due": "Due date",
    "priority": "Priority",
    "title": "Title (A–Z)",
}


def _get_owned_task_or_404(task_id: int) -> Task:
    """Fetch a task, ensuring it belongs to the logged-in user."""
    task = models.get_task(task_id)
    if task is None or task.user_id != current_user.id:
        abort(404)
    return task


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

    tasks = models.list_tasks(
        current_user.id,
        status=status,
        category=category,
        priority=priority,
        search=search,
        sort=sort,
    )

    return render_template(
        "todos/index.html",
        tasks=tasks,
        stats=models.task_stats(current_user.id),
        categories=models.distinct_categories(current_user.id),
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
        models.create_task(
            current_user.id,
            title=form.title.data.strip(),
            notes=(form.notes.data or "").strip(),
            category=(form.category.data or "").strip(),
            priority=form.priority.data,
            due_date=form.due_date.data,
        )
        flash("Task added.", "success")
        return redirect(url_for("todos.index"))

    return render_template("todos/form.html", form=form, title="New task", task=None)


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit(task_id: int):
    task = _get_owned_task_or_404(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        models.update_task(
            task.id,
            title=form.title.data.strip(),
            notes=(form.notes.data or "").strip(),
            category=(form.category.data or "").strip(),
            priority=form.priority.data,
            due_date=form.due_date.data,
        )
        flash("Task updated.", "success")
        return redirect(url_for("todos.index"))

    return render_template("todos/form.html", form=form, title="Edit task", task=task)


@bp.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle(task_id: int):
    task = _get_owned_task_or_404(task_id)
    models.toggle_task(task)
    return redirect(request.referrer or url_for("todos.index"))


@bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete(task_id: int):
    task = _get_owned_task_or_404(task_id)
    models.delete_task(task.id)
    flash("Task deleted.", "info")
    return redirect(request.referrer or url_for("todos.index"))


@bp.route("/tasks/clear-completed", methods=["POST"])
@login_required
def clear_completed():
    deleted = models.clear_completed(current_user.id)
    flash(f"Cleared {deleted} completed task(s).", "info")
    return redirect(url_for("todos.index"))

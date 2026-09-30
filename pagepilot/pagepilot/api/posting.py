"""Posting: Reel Post task builder APIs + Auto Page Scheduler stub page.

Tasks are queued honestly in the DB (Task + one TaskItem per page).
Real publishing happens in the automation engine milestone; "Start Task"
therefore queues the task and says so in the UI.
"""
import json
from flask import Blueprint, render_template, render_template_string, request
from sqlalchemy import func

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Page, ContentPreset, Task, TaskItem, ActivityLog

bp = Blueprint("posting", __name__)


def _body():
    return request.get_json(silent=True) or {}


def _to_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _task_counts(s, task_id):
    rows = (s.query(TaskItem.status, func.count(TaskItem.id))
            .filter(TaskItem.task_id == task_id)
            .group_by(TaskItem.status).all())
    counts = {"queued": 0, "running": 0, "done": 0, "failed": 0, "skipped": 0}
    for st, n in rows:
        counts[st] = n
    return counts


@bp.get("/posting")
def page():
    return render_template("posting.html", active_page="posting",
                           title="Reel Post")


@bp.get("/scheduler")
def scheduler_page():
    # Stub page owned by this module until the scheduler module lands.
    return render_template_string(
        '{% extends "base.html" %}'
        '{% block content %}'
        '<div class="card"><div class="card-head">'
        '<div class="card-title">Auto Page Scheduler</div>'
        '<span class="badge b-amber">UPCOMING</span></div>'
        '<p class="card-sub">Time-based auto posting (cron-style schedules, '
        'repeat rules, per-page timetables) scheduler milestone me aayega.</p>'
        '</div>'
        '{% endblock %}',
        active_page="scheduler", title="Auto Page Scheduler")


@bp.post("/api/tasks")
def create_task():
    s = get_session()
    try:
        b = _body()
        name = (b.get("name") or "").strip() or "Reel Post Task"
        kind = b.get("kind") or "reel_post"
        page_ids = b.get("page_ids") or []
        preset_ids = b.get("preset_ids") or []
        cfg = b.get("config") or {}
        if not page_ids:
            return err("Select at least one page")
        found_pages = s.query(Page).filter(Page.id.in_(page_ids)).count()
        if found_pages != len(set(page_ids)):
            return err("Some pages were not found")
        if preset_ids:
            found_presets = (s.query(ContentPreset)
                             .filter(ContentPreset.id.in_(preset_ids)).count())
            if found_presets != len(set(preset_ids)):
                return err("Some content presets were not found")
        config = {
            "min_spacing": _to_int(cfg.get("min_spacing"), 3),
            "max_spacing": _to_int(cfg.get("max_spacing"), 10),
            "switch_on_errors": _to_int(cfg.get("switch_on_errors"), 10),
            "loop": bool(cfg.get("loop", False)),
            "preset_ids": list(preset_ids),
        }
        task = Task(name=name, kind=kind, status="idle",
                    config_json=json.dumps(config))
        s.add(task)
        s.flush()
        for i, pid in enumerate(page_ids):
            preset_id = preset_ids[i % len(preset_ids)] if preset_ids else None
            s.add(TaskItem(task_id=task.id, page_id=pid,
                           preset_id=preset_id, status="queued"))
        s.add(ActivityLog(action="task_created", status="info",
                          message=f"Task '{name}' queued: {len(page_ids)} page(s)"))
        s.commit()
        data = task.to_dict()
        data["counts"] = _task_counts(s, task.id)
        return ok(data)
    finally:
        s.close()


@bp.get("/api/tasks")
def list_tasks():
    s = get_session()
    try:
        tasks = s.query(Task).order_by(Task.id.desc()).all()
        out = []
        for t in tasks:
            d = t.to_dict()
            d["counts"] = _task_counts(s, t.id)
            out.append(d)
        return ok(out)
    finally:
        s.close()


@bp.get("/api/tasks/<int:task_id>")
def task_detail(task_id):
    s = get_session()
    try:
        task = s.query(Task).filter_by(id=task_id).first()
        if not task:
            return err("Task not found", 404)
        items = (s.query(TaskItem).filter_by(task_id=task_id)
                 .order_by(TaskItem.id).all())
        page_ids = [i.page_id for i in items]
        pg = {p.id: p.name for p in s.query(Page).filter(
            Page.id.in_(page_ids)).all()} if page_ids else {}
        pr = {p.id: p.title for p in s.query(ContentPreset).all()}
        item_dicts = []
        for i in items:
            d = i.to_dict()
            d["page"] = pg.get(i.page_id, f"#{i.page_id}")
            d["preset"] = pr.get(i.preset_id, "—") if i.preset_id else "—"
            item_dicts.append(d)
        data = task.to_dict()
        data["items"] = item_dicts
        data["counts"] = _task_counts(s, task_id)
        return ok(data)
    finally:
        s.close()


@bp.post("/api/tasks/<int:task_id>/cancel")
def cancel_task(task_id):
    s = get_session()
    try:
        task = s.query(Task).filter_by(id=task_id).first()
        if not task:
            return err("Task not found", 404)
        n = (s.query(TaskItem)
             .filter(TaskItem.task_id == task_id,
                     TaskItem.status == "queued")
             .update({"status": "skipped"}, synchronize_session=False))
        task.status = "paused"
        s.add(ActivityLog(
            action="task_cancelled", status="info",
            message=f"Task '{task.name}' paused, {n} queued item(s) skipped"))
        s.commit()
        return ok({"cancelled": n, "task": task.to_dict()})
    finally:
        s.close()

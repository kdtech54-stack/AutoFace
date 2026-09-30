"""Scheduler API: auto-scheduler Run/Stop + scheduled jobs CRUD.

The topbar 'Run' button toggles the background worker that executes
queued TaskItems with human-like pacing.
"""
from datetime import datetime

from flask import Blueprint, request

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import ScheduledJob, Task, TaskItem
from pagepilot.automation import worker
from pagepilot.automation.worker import _next_time  # reuse time math

bp = Blueprint("scheduler", __name__)


@bp.get("/api/scheduler/status")
def status():
    s = get_session()
    try:
        queued = s.query(TaskItem).filter_by(status="queued").count()
        jobs = s.query(ScheduledJob).filter_by(enabled=True).count()
        return ok({"running": worker.is_running(),
                   "queued": queued, "jobs": jobs})
    finally:
        s.close()


@bp.post("/api/scheduler/toggle")
def toggle():
    if worker.is_running():
        return ok(worker.stop())
    return ok(worker.start())


@bp.get("/api/scheduler/jobs")
def list_jobs():
    s = get_session()
    try:
        jobs = s.query(ScheduledJob).order_by(ScheduledJob.id).all()
        tasks = {t.id: t.name for t in s.query(Task).all()}
        out = []
        for j in jobs:
            d = j.to_dict()
            d["task_name"] = tasks.get(j.task_id, "")
            out.append(d)
        return ok(out)
    finally:
        s.close()


@bp.post("/api/scheduler/jobs")
def create_job():
    """Body: {name, task_id, kind: interval|daily, hours | time: HH:MM}"""
    b = request.get_json(force=True, silent=True) or {}
    name = (b.get("name") or "").strip() or "Scheduled job"
    task_id = b.get("task_id")
    kind = (b.get("kind") or "interval").strip()
    s = get_session()
    try:
        if not s.query(Task).filter_by(id=task_id).first():
            return err("Task not found")
        if kind == "daily":
            t = (b.get("time") or "09:00").strip()
            try:
                h, m = t.split(":")
                int(h)
                int(m)
            except Exception:
                return err("time must be HH:MM")
            cron_expr = f"daily:{int(h):02d}:{int(m):02d}"
        else:
            try:
                hours = float(b.get("hours") or 6)
                assert hours > 0
            except Exception:
                return err("hours must be a positive number")
            cron_expr = f"interval:{hours}"
        job = ScheduledJob(name=name, task_id=task_id, cron_expr=cron_expr,
                           enabled=True)
        job.next_run = _next_time(job)
        s.add(job)
        s.commit()
        return ok(job.to_dict())
    finally:
        s.close()


@bp.delete("/api/scheduler/jobs")
def delete_jobs():
    b = request.get_json(force=True, silent=True) or {}
    try:
        ids = [int(i) for i in (b.get("ids") or [])]
    except (ValueError, TypeError):
        return err("Invalid ids")
    s = get_session()
    try:
        n = (s.query(ScheduledJob).filter(ScheduledJob.id.in_(ids))
             .delete(synchronize_session=False))
        s.commit()
        return ok({"deleted": n})
    finally:
        s.close()


@bp.post("/api/scheduler/jobs/<int:job_id>/toggle")
def toggle_job(job_id):
    s = get_session()
    try:
        job = s.query(ScheduledJob).filter_by(id=job_id).first()
        if not job:
            return err("Job not found")
        job.enabled = not job.enabled
        s.commit()
        return ok(job.to_dict())
    finally:
        s.close()

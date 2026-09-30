"""Comments & Engagement page + warm-up / comment-reply task APIs."""
import json

from flask import Blueprint, render_template, request

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Account, Page, Task, TaskItem, ActivityLog

bp = Blueprint("engagement", __name__)


@bp.get("/engagement")
def page():
    return render_template("engagement.html", active_page="engagement",
                           title="Comments & Engagement")


@bp.post("/api/tasks/warmup")
def create_warmup():
    """Body: {name?, account_ids: [...], minutes} -> kind=warmup task."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        account_ids = [int(i) for i in (body.get("account_ids") or [])]
    except (ValueError, TypeError):
        return err("Invalid account ids")
    if not account_ids:
        return err("Select at least one account")
    try:
        minutes = max(1, min(60, int(body.get("minutes") or 10)))
    except (ValueError, TypeError):
        return err("Invalid minutes")
    s = get_session()
    try:
        found = s.query(Account).filter(
            Account.id.in_(account_ids)).count()
        if found != len(set(account_ids)):
            return err("Some accounts were not found")
        name = (body.get("name") or "").strip() or "Warm-up Task"
        task = Task(name=name, kind="warmup", status="idle",
                    config_json=json.dumps({"minutes": minutes}))
        s.add(task)
        s.flush()
        for aid in account_ids:
            s.add(TaskItem(task_id=task.id, page_id=None,
                           account_id=aid, status="queued"))
        s.add(ActivityLog(
            action="task_created", status="info",
            message=f"Warm-up task '{name}': {len(account_ids)} account(s), "
                    f"{minutes} min each"))
        s.commit()
        return ok(task.to_dict())
    finally:
        s.close()


@bp.post("/api/tasks/engagement")
def create_engagement():
    """Body: {name?, page_ids: [...], replies: "a\\n\\nb", max_replies}."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        page_ids = [int(i) for i in (body.get("page_ids") or [])]
    except (ValueError, TypeError):
        return err("Invalid page ids")
    if not page_ids:
        return err("Select at least one page")
    raw = body.get("replies") or ""
    if isinstance(raw, list):
        replies = [str(r).strip() for r in raw if str(r).strip()]
    else:
        replies = [b.strip() for b in str(raw).split("\n\n") if b.strip()]
    if not replies:
        return err("Add at least one reply text (spintax allowed)")
    try:
        max_replies = max(1, min(50, int(body.get("max_replies") or 10)))
    except (ValueError, TypeError):
        return err("Invalid max_replies")
    s = get_session()
    try:
        pages = s.query(Page).filter(Page.id.in_(page_ids)).all()
        if len(pages) != len(set(page_ids)):
            return err("Some pages were not found")
        name = (body.get("name") or "").strip() or "Comment Reply Task"
        task = Task(
            name=name, kind="comment_reply", status="idle",
            config_json=json.dumps({"replies": replies,
                                    "max_replies": max_replies}))
        s.add(task)
        s.flush()
        for p in pages:
            s.add(TaskItem(task_id=task.id, page_id=p.id,
                           account_id=None, status="queued"))
        s.add(ActivityLog(
            action="task_created", status="info",
            message=f"Comment-reply task '{name}': {len(pages)} page(s), "
                    f"up to {max_replies} replies each"))
        s.commit()
        return ok(task.to_dict())
    finally:
        s.close()

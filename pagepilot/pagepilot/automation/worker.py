"""Background worker: executes queued TaskItems with human-like pacing.

- Picks the next due queued item (any task not paused).
- Random spacing between actions (min/max seconds from task config or settings).
- On repeated errors for one account (>= switch_on_errors): skip that
  account's remaining items this pass (switch account on errors).
- Loop toggle: a task with loop=true re-queues its items when finished.
- Scheduler jobs (interval/daily) re-run their task on schedule.
"""
import json
import os
import random
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy import or_

from pagepilot.database import get_session
from pagepilot.models import (Account, Caption, MediaAsset, Page, Setting,
                              Task, TaskItem, ActivityLog, ScheduledJob,
                              ContentPreset, PostedHash)
from pagepilot.utils import macros
from .browser import new_context, close_context
from .auth import ensure_logged_in
from . import poster

_state = {"running": False, "thread": None, "current": None,
          "acct_errors": {}}


def is_running() -> bool:
    return _state["running"]


def _setting(key: str, default: str) -> str:
    s = get_session()
    try:
        row = s.query(Setting).filter_by(key=key).first()
        return row.value if row else default
    finally:
        s.close()


def _task_cfg(task) -> dict:
    try:
        cfg = json.loads(task.config_json or "{}")
    except Exception:
        cfg = {}
    cfg.setdefault("min_spacing", int(_setting("min_spacing", "3")))
    cfg.setdefault("max_spacing", int(_setting("max_spacing", "10")))
    cfg.setdefault("switch_on_errors", int(_setting("switch_on_errors", "10")))
    cfg.setdefault("loop", False)
    return cfg


def _pick_caption(s, preset) -> str:
    caps = (s.query(Caption).filter_by(preset_id=preset.id)
            .order_by(Caption.sort_order).all())
    text = random.choice(caps).text if caps else (preset.template or "")
    return macros.render(text)


def _pick_media(s, preset):
    assets = s.query(MediaAsset).filter_by(preset_id=preset.id).all()
    assets = [a for a in assets if a.filepath and os.path.exists(a.filepath)]
    return random.choice(assets) if assets else None


def _pick_fresh_media(s, preset, page_id):
    """Duplicate guard: return a preset asset not posted to this page
    within the duplicate window, or None when everything was used."""
    from pagepilot.utils.hashing import sha256_file
    try:
        days = max(1, int(_setting("dup_guard_days", "30")))
    except (ValueError, TypeError):
        days = 30
    cutoff = datetime.utcnow() - timedelta(days=days)
    assets = s.query(MediaAsset).filter_by(preset_id=preset.id).all()
    assets = [a for a in assets if a.filepath and os.path.exists(a.filepath)]
    random.shuffle(assets)
    for a in assets:
        try:
            h = sha256_file(a.filepath)
        except Exception:
            continue
        seen = (s.query(PostedHash)
                .filter(PostedHash.page_id == page_id,
                        PostedHash.sha256 == h,
                        PostedHash.posted_at >= cutoff).first())
        if not seen:
            return a
    return None


def _run_special(s, item, task):
    """Execute warmup / comment_reply task items (no page publishing)."""
    cfg = _task_cfg(task)
    kind = task.kind
    item.status = "running"
    item.attempts += 1
    s.commit()
    item_id = item.id
    if kind == "warmup":
        acc = s.query(Account).filter_by(id=item.account_id).first()
        if not acc:
            return _fail(s, item, None, None, "warmup",
                         "account not found")
        from .warmup import run_warmup
        res = run_warmup(acc.id, int(cfg.get("minutes", 10)))
        action = "warmup"
        acc_id, page_obj = acc.id, None
    else:  # comment_reply
        page_obj = s.query(Page).filter_by(id=item.page_id).first()
        acc = (s.query(Account).filter_by(id=page_obj.account_id).first()
               if page_obj and page_obj.account_id else None)
        if not page_obj or not acc:
            return _fail(s, item, None, page_obj, "comment_reply",
                         "page/account not found")
        from .engagement import auto_reply
        replies = cfg.get("replies") or []
        res = auto_reply(acc.id, page_obj.id, replies,
                         int(cfg.get("max_replies", 10)))
        action = "comment_reply"
        acc_id = acc.id
    item = s.query(TaskItem).filter_by(id=item_id).first()
    if res.get("ok"):
        item.status = "done"
        item.executed_at = datetime.utcnow()
        item.result_json = json.dumps(
            {"ok": True, **{k: v for k, v in res.items() if k != "ok"}})
        _log(s, acc_id, page_obj.id if page_obj else None, action, "ok",
             f"{action} done: {res}")
    else:
        item.status = "failed"
        item.executed_at = datetime.utcnow()
        item.result_json = json.dumps({"error": res.get("error", "failed")})
        _log(s, acc_id, page_obj.id if page_obj else None, action, "failed",
             res.get("error", "failed")[:300])
    _maybe_finish_task(s, task)
    s.commit()
    return res


def _log(s, account_id, page_id, action, status, message):
    s.add(ActivityLog(account_id=account_id, page_id=page_id,
                      action=action, status=status, message=message[:500]))


def execute_item(item_id: int) -> dict:
    """Execute one queued TaskItem. Returns {ok, ...}."""
    s = get_session()
    try:
        item = s.query(TaskItem).filter_by(id=item_id).first()
        if not item or item.status != "queued":
            return {"ok": False, "error": "item not queued"}
        task = s.query(Task).filter_by(id=item.task_id).first()
        if task and task.kind in ("warmup", "comment_reply"):
            return _run_special(s, item, task)
        page = s.query(Page).filter_by(id=item.page_id).first()
        if not page:
            item.status = "failed"
            item.result_json = json.dumps({"error": "page deleted"})
            s.commit()
            return {"ok": False, "error": "page deleted"}
        account = (s.query(Account).filter_by(id=page.account_id).first()
                   if page.account_id else None)
        if not account:
            item.status = "failed"
            item.result_json = json.dumps({"error": "no owning account"})
            _log(s, None, page.id, "reel_published" if (task and task.kind == "reel_post") else "post_published",
                 "failed", f"{page.name}: no owning account")
            s.commit()
            return {"ok": False, "error": "no owning account"}

        cfg = _task_cfg(task) if task else {}
        preset = (s.query(ContentPreset).filter_by(id=item.preset_id).first()
                  if item.preset_id else None)

        caption = _pick_caption(s, preset) if preset else ""
        media = _pick_media(s, preset) if preset else None
        kind = task.kind if task else "reel_post"
        action_name = ("reel_published" if kind == "reel_post"
                       else "post_published")
        if kind == "reel_post" and not media:
            item.status = "failed"
            item.result_json = json.dumps({"error": "no media in preset"})
            _log(s, account.id, page.id, action_name, "failed",
                 f"{page.name}: preset has no media files")
            s.commit()
            return {"ok": False, "error": "no media in preset"}
        # duplicate guard: pick media not posted to this page recently
        if media and preset and _setting("dup_guard", "1") != "0":
            fresh = _pick_fresh_media(s, preset, page.id)
            if fresh is None:
                item.status = "failed"
                item.result_json = json.dumps(
                    {"error": "duplicate guard: all preset media already "
                              "posted to this page recently"})
                _log(s, account.id, page.id, action_name, "failed",
                     f"{page.name}: duplicate guard blocked "
                     f"(all media used recently)")
                s.commit()
                return {"ok": False, "error": "duplicate guard blocked"}
            media = fresh

        item.status = "running"
        item.attempts += 1
        s.commit()
        item_id_keep, page_id_keep, acc_id_keep = item.id, page.id, account.id
        page_name, page_url = page.name, page.url
        media_path = media.filepath if media else None
        # uniquifier: publish a hash-unique copy, original stays untouched
        tmp_copy = None
        if media_path and _setting("uniquify_media", "1") != "0":
            try:
                from pagepilot.utils.uniquify import uniquify as _uq
                tmp_copy = _uq(media_path)
                if tmp_copy:
                    media_path = tmp_copy
            except Exception:
                tmp_copy = None

        # --- browser work (outside long DB txn) ---
        try:
            ctx = new_context(account)
        except Exception as e:
            return _fail(s, item, account, page, action_name,
                         f"browser failed: {e}"[:200])
        try:
            state, fbp = ensure_logged_in(ctx, account)
            if state != "logged_in" or fbp is None:
                try:
                    if fbp is not None:
                        fbp.close()
                except Exception:
                    pass
                account.status = "checkpoint" if state == "checkpoint" else account.status
                return _fail(s, item, account, page, action_name,
                             f"login failed: {state}"[:150])
            if kind == "reel_post":
                res = poster.publish_reel(fbp, caption, media_path)
            else:
                res = poster.publish_post(fbp, page_url or "https://www.facebook.com/", caption, media_path)
            try:
                fbp.close()
            except Exception:
                pass
        except Exception as e:
            res = {"ok": False, "error": str(e)[:200]}
        finally:
            close_context(ctx)
            if tmp_copy and os.path.exists(tmp_copy):
                try:
                    os.remove(tmp_copy)
                except Exception:
                    pass

        # --- record outcome ---
        item = s.query(TaskItem).filter_by(id=item_id_keep).first()
        account = s.query(Account).filter_by(id=acc_id_keep).first()
        page = s.query(Page).filter_by(id=page_id_keep).first()
        if res.get("ok"):
            item.status = "done"
            item.executed_at = datetime.utcnow()
            item.result_json = json.dumps({"ok": True})
            # remember this media's hash for the duplicate guard
            try:
                from pagepilot.utils.hashing import sha256_file
                if (media and media.filepath
                        and os.path.exists(media.filepath)):
                    s.add(PostedHash(
                        sha256=sha256_file(media.filepath),
                        page_id=page_id_keep, preset_id=item.preset_id,
                        media_path=media.filepath))
            except Exception:
                pass
            _log(s, account.id if account else None, page.id if page else None,
                 action_name, "ok",
                 f"{page_name}: published ({kind})")
            _state["acct_errors"].pop(acc_id_keep, None)
            _maybe_finish_task(s, task)
            s.commit()
            return {"ok": True}
        return _fail(s, item, account, page, action_name,
                     res.get("error", "publish failed")[:200], cfg)
    finally:
        s.close()


def _fail(s, item, account, page, action_name, error, cfg=None):
    if item:
        item.status = "failed"
        item.executed_at = datetime.utcnow()
        item.result_json = json.dumps({"error": error})
    acc_id = account.id if account else None
    _log(s, acc_id, page.id if page else None, action_name, "failed",
         f"{page.name if page else '?'}: {error}")
    if acc_id and cfg:
        n = _state["acct_errors"].get(acc_id, 0) + 1
        _state["acct_errors"][acc_id] = n
    if item and item.task_id:
        task = s.query(Task).filter_by(id=item.task_id).first()
        _maybe_finish_task(s, task)
    s.commit()
    return {"ok": False, "error": error}


def _maybe_finish_task(s, task):
    if not task:
        return
    left = s.query(TaskItem).filter_by(task_id=task.id, status="queued").count()
    if left == 0 and task.status in ("idle", "running"):
        task.status = "done"


def _next_due(s):
    now = datetime.utcnow()
    return (s.query(TaskItem)
            .join(Task, TaskItem.task_id == Task.id)
            .filter(TaskItem.status == "queued",
                    Task.status != "paused",
                    or_(TaskItem.scheduled_at.is_(None),
                        TaskItem.scheduled_at <= now))
            .order_by(TaskItem.id).first())


def _process_due_jobs(s):
    """Re-run scheduled jobs whose time has come."""
    now = datetime.utcnow()
    for job in s.query(ScheduledJob).filter_by(enabled=True).all():
        due = job.next_run is not None and job.next_run <= now
        if not due:
            continue
        task = s.query(Task).filter_by(id=job.task_id).first()
        if task:
            (s.query(TaskItem).filter_by(task_id=task.id)
             .update({"status": "queued", "attempts": 0},
                     synchronize_session=False))
            task.status = "running"
            _log(s, None, None, "task_created", "info",
                 f"Scheduled job '{job.name}' re-queued task '{task.name}'")
        job.next_run = _next_time(job)
    s.commit()


def _next_time(job):
    # cron_expr formats: "interval:6" (every 6h) or "daily:HH:MM"
    try:
        kind, val = (job.cron_expr or "").split(":", 1)
        now = datetime.utcnow()
        if kind == "interval":
            return now + timedelta(hours=float(val))
        if kind == "daily":
            h, m = val.split(":")
            nxt = now.replace(hour=int(h), minute=int(m),
                              second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
            return nxt
    except Exception:
        pass
    return datetime.utcnow() + timedelta(hours=24)


def _loop():
    idle_rounds = 0
    while _state["running"]:
        s = get_session()
        try:
            _process_due_jobs(s)
            item = _next_due(s)
            if item is None:
                # loop toggle: re-queue finished loop tasks
                requeued = False
                for task in s.query(Task).filter_by(status="done").all():
                    cfg = _task_cfg(task)
                    if cfg.get("loop"):
                        (s.query(TaskItem).filter_by(task_id=task.id)
                         .update({"status": "queued", "attempts": 0},
                                 synchronize_session=False))
                        task.status = "running"
                        requeued = True
                if requeued:
                    s.commit()
                    continue
                s.commit()
                idle_rounds += 1
                if idle_rounds % 4 == 0:
                    _state["acct_errors"].clear()
                time.sleep(15)
                continue
            idle_rounds = 0
            # switch-account-on-errors: skip accounts with too many errors
            pg = s.query(Page).filter_by(id=item.page_id).first()
            task = s.query(Task).filter_by(id=item.task_id).first()
            cfg = _task_cfg(task) if task else {}
            acc_id = pg.account_id if pg else None
            if acc_id and _state["acct_errors"].get(acc_id, 0) >= cfg.get("switch_on_errors", 10):
                item.status = "skipped"
                item.result_json = json.dumps({"error": "skipped: account error threshold"})
                s.commit()
                continue
            item_id = item.id
            min_s, max_s = cfg.get("min_spacing", 3), cfg.get("max_spacing", 10)
            s.commit()
        finally:
            s.close()
        _state["current"] = item_id
        execute_item(item_id)
        _state["current"] = None
        time.sleep(random.uniform(min_s, max_s if max_s >= min_s else min_s))


def start() -> dict:
    if _state["running"]:
        return {"running": True, "note": "already running"}
    _state["running"] = True
    _state["acct_errors"] = {}
    t = threading.Thread(target=_loop, daemon=True)
    _state["thread"] = t
    t.start()
    return {"running": True}


def stop() -> dict:
    _state["running"] = False
    return {"running": False}

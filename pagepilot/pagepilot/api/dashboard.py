"""Dashboard: page + stats/activity/log APIs."""
from datetime import date, timedelta
from flask import Blueprint, render_template, jsonify
from sqlalchemy import func

from pagepilot.database import get_session
from pagepilot.models import (Account, Proxy, ContentPreset, TaskItem,
                              ActivityLog, Page)

bp = Blueprint("dashboard", __name__)

LIVE_STATUSES = ("live", "logged_in")


@bp.get("/dashboard")
def page():
    return render_template("dashboard.html", active_page="dashboard",
                           title="Dashboard")


@bp.get("/api/dashboard/stats")
def stats():
    s = get_session()
    try:
        total = s.query(Account).count()
        live = s.query(Account).filter(Account.status.in_(LIVE_STATUSES)).count()
        checkpoint = s.query(Account).filter(Account.status == "checkpoint").count()
        dead = s.query(Account).filter(Account.status == "dead").count()
        proxies = s.query(Proxy).count()
        proxies_active = s.query(Proxy).filter(Proxy.status == "active").count()
        presets = s.query(ContentPreset).count()
        queued = s.query(TaskItem).filter(TaskItem.status == "queued").count()
        actions_today = s.query(ActivityLog).filter(
            func.date(ActivityLog.ts) == date.today()).count()
        lifetime_posts = s.query(ActivityLog).filter(
            ActivityLog.action.in_(["reel_published", "post_published"]),
            ActivityLog.status == "ok").count()
        return jsonify(ok=True, data={
            "accounts": {"total": total, "live": live,
                         "checkpoint": checkpoint, "dead": dead},
            "proxies": {"total": proxies, "active": proxies_active,
                        "pct": round(proxies_active / proxies * 100) if proxies else 100},
            "presets": presets,
            "queued": queued,
            "actions_today": actions_today,
            "lifetime_posts": lifetime_posts,
        })
    finally:
        s.close()


@bp.get("/api/dashboard/activity")
def activity():
    s = get_session()
    try:
        days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        labels, reels, posts = [], [], []
        for d in days:
            labels.append(d.strftime("%a (%m/%d)"))
            r = s.query(ActivityLog).filter(
                func.date(ActivityLog.ts) == d,
                ActivityLog.action == "reel_published",
                ActivityLog.status == "ok").count()
            p = s.query(ActivityLog).filter(
                func.date(ActivityLog.ts) == d,
                ActivityLog.action == "post_published",
                ActivityLog.status == "ok").count()
            reels.append(r)
            posts.append(p)
        return jsonify(ok=True, data={"labels": labels, "reels": reels,
                                      "posts": posts})
    finally:
        s.close()


@bp.get("/api/dashboard/per-page")
def per_page():
    """Per-page publishing stats: last 7 days + lifetime (analytics)."""
    from datetime import datetime
    s = get_session()
    try:
        since = datetime.utcnow() - timedelta(days=7)
        pub = ["reel_published", "post_published"]
        out = []
        for p in s.query(Page).order_by(Page.name).all():
            week = (s.query(func.count(ActivityLog.id))
                    .filter(ActivityLog.page_id == p.id,
                            ActivityLog.action.in_(pub),
                            ActivityLog.status == "ok",
                            ActivityLog.ts >= since).scalar() or 0)
            total = (s.query(func.count(ActivityLog.id))
                     .filter(ActivityLog.page_id == p.id,
                             ActivityLog.action.in_(pub),
                             ActivityLog.status == "ok").scalar() or 0)
            fails = (s.query(func.count(ActivityLog.id))
                     .filter(ActivityLog.page_id == p.id,
                             ActivityLog.action.in_(pub),
                             ActivityLog.status == "failed",
                             ActivityLog.ts >= since).scalar() or 0)
            out.append({"id": p.id, "name": p.name, "week": week,
                        "total": total, "failed_7d": fails})
        out.sort(key=lambda x: (x["week"], x["total"]), reverse=True)
        return jsonify(ok=True, data=out[:15])
    finally:
        s.close()


@bp.get("/api/dashboard/log")
def log():
    s = get_session()
    try:
        rows = (s.query(ActivityLog)
                .order_by(ActivityLog.ts.desc()).limit(25).all())
        acc = {a.id: (a.display_name or a.username or a.uid)
               for a in s.query(Account).all()}
        from pagepilot.models import Page
        pg = {p.id: p.name for p in s.query(Page).all()}
        return jsonify(ok=True, data=[
            r.to_dict(account_name=acc.get(r.account_id, ""),
                      page_name=pg.get(r.page_id, "")) for r in rows])
    finally:
        s.close()

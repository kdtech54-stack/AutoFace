"""Accounts: fleet management (page + import/check/delete APIs)."""
import json
import re
from datetime import datetime

from flask import Blueprint, render_template, request
from sqlalchemy import func, or_

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Account, AccountCategory, ActivityLog, Page
from pagepilot.utils.security import encrypt

bp = Blueprint("accounts", __name__)

LIVE_STATUSES = ("live", "logged_in")
IMPORT_FORMATS = ("auto", "uid|pass|2fa", "uid|pass", "cookies")


@bp.get("/accounts")
def page():
    return render_template("accounts.html", active_page="accounts",
                           title="Accounts")


# ---------------------------------------------------------------- stats

@bp.get("/api/accounts/stats")
def stats():
    s = get_session()
    try:
        return ok({
            "total": s.query(Account).count(),
            "live": s.query(Account).filter(
                Account.status.in_(LIVE_STATUSES)).count(),
            "logged_in": s.query(Account).filter(
                Account.status == "logged_in").count(),
            "checkpoint": s.query(Account).filter(
                Account.status == "checkpoint").count(),
            "dead": s.query(Account).filter(
                Account.status == "dead").count(),
        })
    finally:
        s.close()


# ---------------------------------------------------------------- list

@bp.get("/api/accounts")
def list_accounts():
    s = get_session()
    try:
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "all").strip()
        category_id = (request.args.get("category_id") or "").strip()
        page_n = max(1, int(request.args.get("page") or 1))
        per_page = min(500, max(1, int(request.args.get("per_page") or 100)))

        query = s.query(Account)
        if q:
            like = "%" + q + "%"
            query = query.filter(or_(
                Account.username.ilike(like),
                Account.uid.ilike(like),
                Account.display_name.ilike(like),
                Account.tags.ilike(like)))
        if status == "live":
            query = query.filter(Account.status.in_(LIVE_STATUSES))
        elif status in ("logged_in", "checkpoint", "dead", "unknown"):
            query = query.filter(Account.status == status)
        if category_id and category_id != "all":
            try:
                query = query.filter(
                    Account.category_id == int(category_id))
            except ValueError:
                pass

        total = query.count()
        pages = max(1, (total + per_page - 1) // per_page)
        page_n = min(page_n, pages)
        rows = (query.order_by(Account.id)
                .offset((page_n - 1) * per_page).limit(per_page).all())
        cat_names = {c.id: c.name for c in s.query(AccountCategory).all()}
        items = []
        for a in rows:
            d = a.to_dict()
            d["category"] = cat_names.get(a.category_id, "")
            items.append(d)
        return ok({"items": items, "total": total, "page": page_n,
                   "per_page": per_page, "pages": pages})
    finally:
        s.close()


# ---------------------------------------------------------------- import

_CUSER_RE = re.compile(r"c_user=([^;\s]+)")


def _parse_line(line, forced):
    """Parse one bulk-import line. Returns dict or None (unparseable)."""
    line = line.strip()
    if not line:
        return None
    fmt = forced
    if fmt == "auto":
        if line.startswith("{"):
            fmt = "cookies_json"
        elif "c_user=" in line:
            fmt = "cookies_raw"
        else:
            fmt = "creds"
    if fmt == "cookies_json":
        try:
            d = json.loads(line)
        except Exception:
            return None
        if not isinstance(d, dict):
            return None
        uid = str(d.get("c_user") or d.get("uid") or "")
        return {"uid": uid, "password": "", "twofa": "",
                "cookies": json.dumps(d)}
    if fmt == "cookies" or fmt == "cookies_raw":
        m = _CUSER_RE.search(line)
        if line.startswith("{"):
            return _parse_line(line, "cookies_json")
        return {"uid": m.group(1) if m else "", "password": "",
                "twofa": "", "cookies": line}
    # credential formats: uid|pass|2fa or uid|pass (| or tab delimited)
    delim = "|" if "|" in line else ("\t" if "\t" in line else None)
    if not delim:
        return None
    parts = [p.strip() for p in line.split(delim)]
    if not parts[0]:
        return None
    return {"uid": parts[0],
            "password": parts[1] if len(parts) > 1 else "",
            "twofa": parts[2] if len(parts) > 2 else "",
            "cookies": ""}


@bp.post("/api/accounts/import")
def import_accounts():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text") or ""
    fmt = (data.get("format") or "auto").strip().lower()
    if fmt not in IMPORT_FORMATS:
        fmt = "auto"
    category_id = data.get("category_id")
    try:
        category_id = int(category_id) if category_id not in (
            None, "", "all") else None
    except (ValueError, TypeError):
        category_id = None

    s = get_session()
    try:
        if category_id is not None and not s.query(AccountCategory).filter_by(
                id=category_id).first():
            return err("Category not found")
        cat = s.query(AccountCategory).filter_by(
            id=category_id).first() if category_id else None

        existing_uids = {r[0] for r in s.query(Account.uid).all()}
        seen_uids, seen_cookies = set(), set()
        imported, skipped = 0, 0
        for raw in text.splitlines():
            parsed = _parse_line(raw, fmt)
            if parsed is None:
                if raw.strip():
                    skipped += 1
                continue
            uid, cookies = parsed["uid"], parsed["cookies"]
            key = ("uid", uid) if uid else ("ck", cookies)
            if key in seen_uids or key in seen_cookies:
                skipped += 1
                continue
            if uid and uid in existing_uids:
                skipped += 1
                continue
            a = Account(
                uid=uid,
                username=uid,
                display_name="",
                password_enc=encrypt(parsed["password"]),
                twofa_enc=encrypt(parsed["twofa"]),
                cookies_enc=encrypt(cookies),
                category_id=category_id,
                status="unknown",
            )
            s.add(a)
            if uid:
                seen_uids.add(("uid", uid))
                existing_uids.add(uid)
            else:
                seen_cookies.add(("ck", cookies))
            imported += 1
        s.add(ActivityLog(
            action="account_import", status="info",
            message="Imported %d accounts, skipped %d (target: %s)" % (
                imported, skipped, cat.name if cat else "Uncategorized")))
        s.commit()
        return ok({"imported": imported, "skipped": skipped})
    finally:
        s.close()


# ---------------------------------------------------------------- delete

@bp.delete("/api/accounts")
def delete_accounts():
    data = request.get_json(force=True, silent=True) or {}
    try:
        ids = [int(i) for i in (data.get("ids") or [])]
    except (ValueError, TypeError):
        return err("Invalid ids")
    if not ids:
        return err("No accounts selected")
    s = get_session()
    try:
        # orphan their pages instead of deleting them
        s.query(Page).filter(Page.account_id.in_(ids)).update(
            {Page.account_id: None}, synchronize_session=False)
        n = s.query(Account).filter(Account.id.in_(ids)).delete(
            synchronize_session=False)
        s.commit()
        return ok({"deleted": n})
    finally:
        s.close()


# ---------------------------------------------------------------- check-live

@bp.post("/api/accounts/check-live")
def check_live():
    """Real live-check via the automation engine (background thread)."""
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get("ids")
    try:
        from pagepilot.automation.checker import check_many
        from pagepilot.automation.browser import engine_available
    except Exception:
        return err("engine_pending")
    if not engine_available():
        return err("engine_pending")
    s = get_session()
    try:
        q = s.query(Account.id)
        if ids != "all":
            try:
                id_list = [int(i) for i in (ids or [])]
            except (ValueError, TypeError):
                return err("Invalid ids")
            q = q.filter(Account.id.in_(id_list))
        id_list = [r[0] for r in q.all()]
    finally:
        s.close()
    if not id_list:
        return err("No accounts selected")
    return ok(check_many(id_list))


# ---------------------------------------------------------------- categories

@bp.get("/api/account-categories")
def cat_list():
    s = get_session()
    try:
        totals = dict(s.query(Account.category_id, func.count(Account.id))
                      .group_by(Account.category_id).all())
        cats = (s.query(AccountCategory)
                .order_by(AccountCategory.name).all())
        return ok([{"id": c.id, "name": c.name,
                    "total": totals.get(c.id, 0)} for c in cats])
    finally:
        s.close()


@bp.get("/api/account-categories/stats")
def cat_stats():
    s = get_session()
    try:
        cats = (s.query(AccountCategory)
                .order_by(AccountCategory.name).all())
        totals = dict(s.query(Account.category_id, func.count(Account.id))
                      .group_by(Account.category_id).all())
        lives = dict(s.query(Account.category_id, func.count(Account.id))
                     .filter(Account.status.in_(LIVE_STATUSES))
                     .group_by(Account.category_id).all())
        return ok({
            "categories": [{"id": c.id, "name": c.name,
                            "total": totals.get(c.id, 0),
                            "live": lives.get(c.id, 0)} for c in cats],
            "all": {"total": s.query(Account).count(),
                    "live": s.query(Account).filter(
                        Account.status.in_(LIVE_STATUSES)).count()},
        })
    finally:
        s.close()


@bp.post("/api/account-categories")
def cat_create():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return err("Name required")
    s = get_session()
    try:
        if s.query(AccountCategory).filter(
                func.lower(AccountCategory.name) == name.lower()).first():
            return err("Category already exists")
        c = AccountCategory(name=name)
        s.add(c)
        s.commit()
        return ok(c.to_dict())
    finally:
        s.close()


@bp.delete("/api/account-categories")
def cat_delete():
    data = request.get_json(force=True, silent=True) or {}
    try:
        ids = [int(i) for i in (data.get("ids") or [])]
    except (ValueError, TypeError):
        return err("Invalid ids")
    if not ids:
        return err("No categories selected")
    s = get_session()
    try:
        s.query(Account).filter(Account.category_id.in_(ids)).update(
            {Account.category_id: None}, synchronize_session=False)
        n = s.query(AccountCategory).filter(
            AccountCategory.id.in_(ids)).delete(synchronize_session=False)
        s.commit()
        return ok({"deleted": n})
    finally:
        s.close()

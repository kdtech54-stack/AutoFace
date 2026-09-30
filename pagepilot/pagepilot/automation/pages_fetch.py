"""Fetch Pages managed by an account.

Strategy: open the account's Pages bookmark / profile pages tab and collect
anchors. All parsing is anchor-based (href + text) so it survives most FB
markup changes. Selectors that do need tuning live in one place below.
"""
import re
import threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from pagepilot.database import get_session
from pagepilot.models import Account, Page, PageCategory, ActivityLog
from .browser import new_context, close_context
from .auth import ensure_logged_in

# Tune here if Facebook changes its pages surfaces.
STRATEGY_URLS = [
    "https://www.facebook.com/bookmarks/pages",
    "https://www.facebook.com/me/pages",
]

_UID_PATTERNS = [
    re.compile(r"facebook\.com/(?:[^/?#]+-)?(\d{6,})/?"),
    re.compile(r"facebook\.com/profile\.php\?[^#]*\bid=(\d{6,})"),
]


def _extract_pages(page) -> list:
    """Return [{page_uid, name, url}] found on the current FB page."""
    try:
        links = page.eval_on_selector_all(
            "a", "els => els.map(e => ({href: e.href || '', text: (e.innerText || '').trim()}))")
    except Exception:
        return []
    seen, out = set(), []
    for l in links:
        href = l.get("href", "")
        text = l.get("text", "")
        if "facebook.com" not in href or len(text) < 2 or len(text) > 80:
            continue
        uid = None
        for pat in _UID_PATTERNS:
            m = pat.search(href)
            if m:
                uid = m.group(1)
                break
        if not uid or uid in seen:
            continue
        # skip profile-ish links (people), keep page-ish ones
        path = urlparse(href).path.strip("/")
        if path in ("", "me") or "?" in href and "id=" not in href:
            continue
        seen.add(uid)
        slug = path.split("/")[0].split("-")[0]
        out.append({"page_uid": uid,
                    "name": text.split("\n")[0][:120],
                    "slug": slug[:120], "url": href.split("?")[0]})
    return out


def _default_category_id(s):
    c = s.query(PageCategory).filter_by(name="Default").first()
    return c.id if c else None


def fetch_pages_for_account(account_id: int) -> dict:
    s = get_session()
    try:
        acc = s.query(Account).filter_by(id=account_id).first()
        if not acc:
            return {"ok": False, "id": account_id, "error": "not found"}
        label = acc.display_name or acc.username or acc.uid or f"#{acc.id}"
        try:
            ctx = new_context(acc)
        except Exception as e:
            return {"ok": False, "id": account_id,
                    "error": f"browser failed: {e}"[:200]}
        try:
            state, fbp = ensure_logged_in(ctx, acc)
            if state != "logged_in":
                if fbp is not None:
                    try:
                        fbp.close()
                    except Exception:
                        pass
                return {"ok": False, "id": account_id,
                        "error": f"login failed: {state}"[:120]}
            found = []
            for url in STRATEGY_URLS:
                try:
                    fbp.goto(url, wait_until="domcontentloaded")
                    fbp.wait_for_timeout(4500)
                    batch = _extract_pages(fbp)
                    for b in batch:
                        if b["page_uid"] not in {f["page_uid"] for f in found}:
                            found.append(b)
                except Exception:
                    continue
            try:
                fbp.close()
            except Exception:
                pass
            cat_id = _default_category_id(s)
            added, updated = 0, 0
            for f in found:
                row = s.query(Page).filter_by(
                    account_id=acc.id, page_uid=f["page_uid"]).first()
                if row:
                    row.name = f["name"] or row.name
                    row.slug = f["slug"] or row.slug
                    row.url = f["url"] or row.url
                    row.last_sync = datetime.utcnow()
                    updated += 1
                else:
                    s.add(Page(account_id=acc.id, page_uid=f["page_uid"],
                               name=f["name"], slug=f["slug"], url=f["url"],
                               category_id=cat_id, status="active",
                               last_sync=datetime.utcnow()))
                    added += 1
            s.add(ActivityLog(
                account_id=acc.id, action="page_fetch", status="ok",
                message=f"{label}: {added} new, {updated} updated"))
            s.commit()
            return {"ok": True, "id": account_id,
                    "added": added, "updated": updated}
        except Exception as e:
            s.rollback()
            return {"ok": False, "id": account_id, "error": str(e)[:200]}
        finally:
            close_context(ctx)
    finally:
        s.close()


def _fetch_many_sync(ids):
    for i in ids:
        try:
            fetch_pages_for_account(i)
        except Exception:
            continue


def fetch_many(ids) -> dict:
    t = threading.Thread(target=_fetch_many_sync, args=(list(ids),),
                         daemon=True)
    t.start()
    return {"started": len(ids),
            "note": "Page fetch running in background — refresh the list."}

"""Live-status checker: logged_in | checkpoint | dead | unknown."""
import threading
from datetime import datetime

from pagepilot.database import get_session
from pagepilot.models import Account, ActivityLog
from .browser import new_context, close_context
from .auth import ensure_logged_in

FINAL = {"logged_in": "logged_in", "checkpoint": "checkpoint",
         "logged_out": "dead", "dead": "dead",
         "no_credentials": "unknown", "unknown": "unknown"}


def _map(state: str) -> str:
    base = state.split(":")[0].strip()
    return FINAL.get(base, "unknown")


def check_account(account_id: int) -> dict:
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
            state, page = ensure_logged_in(ctx, acc)
            status = _map(state)
            acc.status = status
            acc.last_check = datetime.utcnow()
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            s.add(ActivityLog(
                account_id=acc.id, action="live_check",
                status="ok" if status == "logged_in" else "info",
                message=f"{label}: {status}"))
            s.commit()
            return {"ok": True, "id": account_id, "status": status}
        except Exception as e:
            s.rollback()
            return {"ok": False, "id": account_id, "error": str(e)[:200]}
        finally:
            close_context(ctx)
    finally:
        s.close()


def _check_many_sync(ids):
    for i in ids:
        try:
            check_account(i)
        except Exception:
            continue


def check_many(ids) -> dict:
    """Run checks in a background thread; UI polls via stats/list."""
    t = threading.Thread(target=_check_many_sync, args=(list(ids),),
                         daemon=True)
    t.start()
    return {"started": len(ids),
            "note": "Live checks running in background — refresh the list."}

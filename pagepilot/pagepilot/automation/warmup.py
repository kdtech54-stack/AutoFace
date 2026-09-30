"""Warm-up mode: human-like activity for new accounts.

Scrolls the feed, likes a few visible posts and watches a reel or two,
all with randomized timing. Everything is bounded and logged.
"""
import random
import time

from pagepilot.database import get_session
from pagepilot.models import Account, ActivityLog
from .browser import new_context, close_context
from .auth import ensure_logged_in


def run_warmup(account_id: int, minutes: int = 10) -> dict:
    minutes = max(1, min(60, int(minutes or 10)))
    s = get_session()
    try:
        acc = s.query(Account).filter_by(id=account_id).first()
        if not acc:
            return {"ok": False, "error": "account not found"}
        label = acc.display_name or acc.username or acc.uid or f"#{acc.id}"
        try:
            ctx = new_context(acc)
        except Exception as e:
            return {"ok": False, "error": f"browser failed: {e}"[:150]}
        try:
            state, page = ensure_logged_in(ctx, acc)
            if state != "logged_in" or page is None:
                try:
                    if page is not None:
                        page.close()
                except Exception:
                    pass
                return {"ok": False, "error": f"login failed: {state}"[:120]}
            end = time.time() + minutes * 60
            likes = 0
            max_likes = random.randint(2, 6)
            try:
                page.goto("https://www.facebook.com/",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                while time.time() < end:
                    for _ in range(random.randint(2, 5)):
                        try:
                            page.mouse.wheel(0, random.randint(400, 900))
                        except Exception:
                            pass
                        page.wait_for_timeout(random.randint(1200, 3000))
                    if likes < max_likes and random.random() < 0.5:
                        try:
                            btns = page.locator(
                                "[aria-label='Like'][role='button']").all()
                            visible = [b for b in btns if b.is_visible()]
                            if visible:
                                random.choice(visible).click(timeout=4000)
                                likes += 1
                                page.wait_for_timeout(
                                    random.randint(2000, 5000))
                        except Exception:
                            pass
                    if random.random() < 0.25 and time.time() < end - 20:
                        try:
                            page.goto("https://www.facebook.com/reels/",
                                      wait_until="domcontentloaded")
                            page.wait_for_timeout(random.randint(6000, 14000))
                            page.goto("https://www.facebook.com/",
                                      wait_until="domcontentloaded")
                            page.wait_for_timeout(3000)
                        except Exception:
                            pass
            finally:
                try:
                    page.close()
                except Exception:
                    pass
            s.add(ActivityLog(
                account_id=acc.id, action="warmup", status="ok",
                message=f"{label}: warm-up {minutes} min, {likes} likes"))
            s.commit()
            return {"ok": True, "likes": likes, "minutes": minutes}
        finally:
            close_context(ctx)
    finally:
        s.close()

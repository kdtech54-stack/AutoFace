"""Comment auto-reply: reply to comments on a page's recent posts.

Walks the page's recent posts, finds unreplied comments (fingerprinted in
the DB so we never reply twice) and replies with a spintax-rendered message.
Selectors are best-effort with debug screenshots on failure.
"""
import hashlib
import random
import time

from pagepilot.database import get_session
from pagepilot.models import Account, Page, RepliedComment, ActivityLog
from pagepilot.utils import macros
from .browser import new_context, close_context
from .auth import ensure_logged_in
from .poster import debug_shot, _first_visible, SELECTORS


def _fingerprint(*parts: str) -> str:
    raw = "|".join(parts).strip().lower().encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()[:32]


def auto_reply(account_id: int, page_id: int, replies: list,
               max_replies: int = 10) -> dict:
    max_replies = max(1, min(50, int(max_replies or 10)))
    replies = [r for r in (replies or []) if r and r.strip()]
    s = get_session()
    try:
        acc = s.query(Account).filter_by(id=account_id).first()
        page = s.query(Page).filter_by(id=page_id).first()
        if not acc or not page:
            return {"ok": False, "error": "account/page not found"}
        if not replies:
            return {"ok": False, "error": "no reply texts configured"}
        try:
            ctx = new_context(acc)
        except Exception as e:
            return {"ok": False, "error": f"browser failed: {e}"[:150]}
        done = 0
        try:
            state, fbp = ensure_logged_in(ctx, acc)
            if state != "logged_in" or fbp is None:
                try:
                    if fbp is not None:
                        fbp.close()
                except Exception:
                    pass
                return {"ok": False, "error": f"login failed: {state}"[:120]}
            try:
                fbp.goto(page.url or "https://www.facebook.com/",
                         wait_until="domcontentloaded")
                fbp.wait_for_timeout(5000)
                try:
                    links = fbp.eval_on_selector_all(
                        "a[href*='/posts/'], a[href*='/reel/']",
                        "els => [...new Set(els.map(e => e.href.split('?')[0]))].slice(0, 5)")
                except Exception:
                    links = []
                for link in links or []:
                    if done >= max_replies:
                        break
                    try:
                        fbp.goto(link, wait_until="domcontentloaded")
                        fbp.wait_for_timeout(4000)
                        for _ in range(3):
                            more = _first_visible(
                                fbp, "div[role='button']:has-text('View more comments')")
                            if not more:
                                break
                            try:
                                more.click(timeout=3000)
                                fbp.wait_for_timeout(2000)
                            except Exception:
                                break
                        btns = fbp.locator(
                            "div[role='button']:has-text('Reply')").all()
                    except Exception:
                        continue
                    for btn in btns:
                        if done >= max_replies:
                            break
                        try:
                            if not btn.is_visible():
                                continue
                            article = btn.locator(
                                "xpath=ancestor::div[@role='article'][1]")
                            ctext = ""
                            try:
                                ctext = (article.inner_text(timeout=3000)
                                         or "")[:200]
                            except Exception:
                                pass
                            fp = _fingerprint(str(page.id), link, ctext)
                            if s.query(RepliedComment).filter_by(
                                    page_id=page.id,
                                    comment_key=fp).first():
                                continue
                            btn.click(timeout=4000)
                            fbp.wait_for_timeout(1500)
                            editor = _first_visible(
                                fbp, SELECTORS["caption_editor"])
                            if not editor:
                                try:
                                    fbp.keyboard.press("Escape")
                                except Exception:
                                    pass
                                continue
                            msg = macros.render(random.choice(replies))
                            try:
                                editor.fill(msg, timeout=6000)
                            except Exception:
                                editor.click()
                                fbp.keyboard.type(msg, delay=5)
                            fbp.wait_for_timeout(1200)
                            fbp.keyboard.press("Enter")
                            fbp.wait_for_timeout(2500)
                            s.add(RepliedComment(page_id=page.id,
                                                 comment_key=fp))
                            s.commit()
                            done += 1
                            time.sleep(random.uniform(3, 8))
                        except Exception:
                            continue
            finally:
                try:
                    fbp.close()
                except Exception:
                    pass
            s.add(ActivityLog(
                account_id=acc.id, page_id=page.id, action="comment_reply",
                status="ok",
                message=f"{page.name}: replied to {done} comment(s)"))
            s.commit()
            return {"ok": True, "replied": done}
        finally:
            close_context(ctx)
    finally:
        s.close()

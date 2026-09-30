"""Facebook login flows.

Order: saved session (persistent profile) -> injected cookies ->
UID/password -> 2FA TOTP (from the stored 2FA secret).

Returns one of: logged_in | checkpoint | logged_out | dead |
no_credentials | unknown
"""
import json

from pagepilot.utils import security


def detect_state(page) -> str:
    """Inspect the current page and decide the account state."""
    try:
        url = page.url or ""
    except Exception:
        return "unknown"
    if "checkpoint" in url:
        return "checkpoint"
    try:
        # Facebook login form present?
        if page.locator("#email").count() and page.locator("#pass").count():
            return "logged_out"
    except Exception:
        pass
    try:
        cookies = page.context.cookies()
        if any(c.get("name") == "c_user" for c in cookies):
            return "logged_in"
    except Exception:
        pass
    return "unknown"


def inject_cookies(context, account) -> bool:
    raw = security.decrypt(account.cookies_enc)
    if not raw:
        return False
    try:
        cookies = []
        raw = raw.strip()
        if raw.startswith("{") or raw.startswith("["):
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for c in items:
                if isinstance(c, dict) and c.get("name"):
                    cookies.append({
                        "name": c["name"], "value": str(c.get("value", "")),
                        "domain": c.get("domain", ".facebook.com"),
                        "path": c.get("path", "/")})
        else:
            for part in raw.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies.append({"name": k.strip(), "value": v.strip(),
                                    "domain": ".facebook.com", "path": "/"})
        if not cookies:
            return False
        context.add_cookies(cookies)
        return True
    except Exception:
        return False


def _dismiss_nags(page):
    """Click 'Not Now' / 'Skip' interstitials if they appear (non-fatal)."""
    for text in ("Not Now", "Skip"):
        try:
            loc = page.locator(
                f"div[role='button']:has-text('{text}'), "
                f"button:has-text('{text}')").first
            if loc.count() and loc.is_visible():
                loc.click(timeout=3000)
                page.wait_for_timeout(1500)
        except Exception:
            continue


def login_with_credentials(page, account) -> str:
    uid = (account.uid or account.username or "").strip()
    pw = security.decrypt(account.password_enc)
    if not uid or not pw:
        return "no_credentials"
    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    try:
        page.fill("#email", uid)
        page.fill("#pass", pw)
        page.locator("button[name='login']").first.click()
    except Exception as e:
        return f"unknown: fill failed {e}"[:120]
    page.wait_for_timeout(5000)
    _dismiss_nags(page)

    # 2FA challenge?
    try:
        code_box = page.locator("input[name='approvals_code']").first
        needs_2fa = ("checkpoint" in (page.url or "")) or (
            code_box.count() and code_box.is_visible())
    except Exception:
        needs_2fa = False
    if needs_2fa:
        secret = security.decrypt(account.twofa_enc).replace(" ", "")
        if not secret:
            return "checkpoint"
        try:
            import pyotp
            code = pyotp.TOTP(secret).now()
            code_box.fill(code)
            page.wait_for_timeout(1500)
            for sel in ("#checkpointSubmitButton",
                        "button:has-text('Continue')"):
                try:
                    btn = page.locator(sel).first
                    if btn.count() and btn.is_visible():
                        btn.click()
                        break
                except Exception:
                    continue
            page.wait_for_timeout(6000)
            _dismiss_nags(page)
        except Exception:
            return "checkpoint"
    return detect_state(page)


def ensure_logged_in(context, account):
    """Return (state, page). Caller must close the page when done."""
    page = context.new_page()
    try:
        if security.decrypt(account.cookies_enc):
            inject_cookies(context, account)
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        state = detect_state(page)
        if state == "logged_out":
            state = login_with_credentials(page, account)
        elif state == "logged_in":
            _dismiss_nags(page)
        return state, page
    except Exception as e:
        try:
            page.close()
        except Exception:
            pass
        return f"unknown: {e}"[:120], None

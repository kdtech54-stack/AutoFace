"""Playwright browser management: one persistent context per account.

Persistent profiles keep Facebook sessions alive between runs (like the
original tool's session handling). Each account may use its assigned proxy.
"""
import os

import config
from pagepilot.database import get_session
from pagepilot.models import Proxy, Setting
from pagepilot.utils import security

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_pw = None


def engine_available() -> bool:
    """True when Playwright is installed and the real engine can run."""
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def _pw_instance():
    global _pw
    if _pw is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
    return _pw


def headless_default() -> bool:
    s = get_session()
    try:
        row = s.query(Setting).filter_by(key="browser_headless").first()
        return (row.value if row else "1") != "0"
    finally:
        s.close()


def proxy_config_for(account) -> dict | None:
    """Playwright proxy dict for the account's assigned proxy (or None)."""
    if not getattr(account, "proxy_id", None):
        return None
    s = get_session()
    try:
        p = s.query(Proxy).filter_by(id=account.proxy_id).first()
        if not p:
            return None
        cfg = {"server": f"{p.protocol}://{p.host}:{p.port}"}
        u = security.decrypt(p.username_enc)
        pw = security.decrypt(p.password_enc)
        if u:
            cfg["username"] = u
        if pw:
            cfg["password"] = pw
        return cfg
    finally:
        s.close()


def new_context(account, headless: bool | None = None):
    """Launch (or reuse) a persistent Chromium context for an account."""
    pw = _pw_instance()
    profile_dir = os.path.join(config.PROFILES_DIR, f"acc_{account.id}")
    os.makedirs(profile_dir, exist_ok=True)
    if headless is None:
        headless = headless_default()
    ctx = pw.chromium.launch_persistent_context(
        profile_dir,
        headless=headless,
        proxy=proxy_config_for(account),
        viewport={"width": 1366, "height": 900},
        user_agent=DESKTOP_UA,
        locale="en-US",
        args=["--disable-blink-features=AutomationControlled"],
    )
    return ctx


def close_context(ctx):
    try:
        ctx.close()
    except Exception:
        pass

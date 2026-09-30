"""Reel / Post publisher via browser automation.

All Facebook-specific selectors live in SELECTORS so they can be tuned in
one place if FB changes markup. Every attempt saves debug screenshots to
DATA_DIR/debug/ on failure so selector issues can be diagnosed remotely.

NOTE: these flows need a first live validation run on the user's machine
against a real account; structure is final, selectors are best-effort.
"""
import os
import time
from datetime import datetime

import config

# ---------------------------------------------------------------- selectors
# If Facebook changes its UI, update these — nothing else needs to change.
SELECTORS = {
    # Reel composer
    "reel_create_urls": [
        "https://www.facebook.com/reels/create/",
        "https://www.facebook.com/reel/create/",
    ],
    "file_input": "input[type='file']",
    "reel_next": "div[role='button']:has-text('Next'), button:has-text('Next')",
    "reel_share": ("div[role='button']:has-text('Share'), button:has-text('Share'),"
                   " div[role='button']:has-text('Publish'), button:has-text('Publish')"),
    "caption_editor": ("[aria-label*='description' i],"
                       " div[contenteditable='true'][role='textbox'],"
                       " [data-lexical-editor='true']"),
    # Page post composer
    "composer_open": ("[aria-label*='Create a post' i],"
                      " [aria-label*=\"What's on your mind\" i]"),
    "post_button": "div[role='button']:has-text('Post'), button:has-text('Post')",
}


def debug_shot(page, name: str):
    try:
        d = os.path.join(config.DATA_DIR, "debug")
        os.makedirs(d, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        page.screenshot(path=os.path.join(d, f"{ts}_{name}.png"))
    except Exception:
        pass


def _first_visible(page, selector: str):
    try:
        loc = page.locator(selector).first
        if loc.count() and loc.is_visible():
            return loc
    except Exception:
        pass
    return None


def _fill_caption(page, caption: str) -> bool:
    if not caption:
        return True
    for sel in SELECTORS["caption_editor"].split(","):
        sel = sel.strip()
        loc = _first_visible(page, sel)
        if not loc:
            continue
        try:
            loc.click(timeout=5000)
            page.wait_for_timeout(800)
            try:
                loc.fill(caption, timeout=8000)
            except Exception:
                page.keyboard.press("ControlOrMeta+a")
                page.keyboard.type(caption, delay=5)
            return True
        except Exception:
            continue
    return False


def _attach_media(page, media_path: str) -> bool:
    try:
        inp = page.locator(SELECTORS["file_input"]).first
        inp.set_input_files(media_path, timeout=30000)
        return True
    except Exception:
        return False


def _click_first(page, selector: str, timeout=15000) -> bool:
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click(timeout=timeout)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- reel

def publish_reel(page, caption: str, media_path: str) -> dict:
    """Publish a reel in the already-logged-in page context."""
    if not media_path or not os.path.exists(media_path):
        return {"ok": False, "error": "media file missing"}
    opened = False
    for url in SELECTORS["reel_create_urls"]:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            if _first_visible(page, SELECTORS["file_input"]):
                opened = True
                break
        except Exception:
            continue
    if not opened:
        debug_shot(page, "reel_composer_missing")
        return {"ok": False, "error": "reel composer not found"}

    if not _attach_media(page, media_path):
        debug_shot(page, "reel_attach_failed")
        return {"ok": False, "error": "media attach failed"}
    # wait for upload to process (Next/Share appears)
    processed = False
    for _ in range(24):  # ~2 min
        page.wait_for_timeout(5000)
        if (_first_visible(page, SELECTORS["reel_next"])
                or _first_visible(page, SELECTORS["reel_share"])):
            processed = True
            break
    if not processed:
        debug_shot(page, "reel_upload_stuck")
        return {"ok": False, "error": "upload did not finish processing"}

    # Optional Next step (trimming etc.) — click through if present
    nxt = _first_visible(page, SELECTORS["reel_next"])
    if nxt:
        try:
            nxt.click(timeout=8000)
            page.wait_for_timeout(4000)
        except Exception:
            pass

    _fill_caption(page, caption)
    page.wait_for_timeout(1500)
    if not _click_first(page, SELECTORS["reel_share"], timeout=20000):
        debug_shot(page, "reel_share_missing")
        return {"ok": False, "error": "Share button not clickable"}
    page.wait_for_timeout(10000)
    return {"ok": True, "note": "share clicked; verify in activity log"}


# ---------------------------------------------------------------- post

def publish_post(page, page_url: str, caption: str,
                 media_path: str | None) -> dict:
    """Publish a regular page post (text + optional media)."""
    try:
        page.goto(page_url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
    except Exception as e:
        return {"ok": False, "error": f"page open failed: {e}"[:150]}
    if not _click_first(page, SELECTORS["composer_open"], timeout=20000):
        debug_shot(page, "post_composer_missing")
        return {"ok": False, "error": "post composer not found"}
    page.wait_for_timeout(2500)
    if media_path and os.path.exists(media_path):
        if not _attach_media(page, media_path):
            debug_shot(page, "post_attach_failed")
            return {"ok": False, "error": "media attach failed"}
        page.wait_for_timeout(6000)
    if not _fill_caption(page, caption):
        debug_shot(page, "post_caption_failed")
        return {"ok": False, "error": "caption editor not found"}
    page.wait_for_timeout(1500)
    if not _click_first(page, SELECTORS["post_button"], timeout=20000):
        debug_shot(page, "post_button_missing")
        return {"ok": False, "error": "Post button not clickable"}
    page.wait_for_timeout(8000)
    return {"ok": True, "note": "post clicked; verify in activity log"}


# ---------------------------------------------------------------- verify helper

def verify_recent_post(page, minutes: int = 15) -> bool:
    """Best-effort: look for a success toast after publishing."""
    try:
        toast = page.locator(
            "div[role='alert']:has-text('shared'), div[role='alert']:has-text('published'),"
            " div:has-text('Your reel was shared'), div:has-text('Post published')").first
        return bool(toast.count())
    except Exception:
        return False

"""AI captions via an OpenAI-compatible API.

The user provides base URL / API key / model in Settings. The key is stored
encrypted (enc: prefix). Without a key the endpoint says so honestly.
"""
from flask import Blueprint, request

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Setting
from pagepilot.utils import security

bp = Blueprint("ai", __name__)


def ai_config():
    s = get_session()
    try:
        rows = {r.key: r.value for r in s.query(Setting).filter(
            Setting.key.in_(["ai_base_url", "ai_api_key", "ai_model"])).all()}
    finally:
        s.close()
    base = (rows.get("ai_base_url") or "https://api.openai.com/v1").rstrip("/")
    key = rows.get("ai_api_key") or ""
    if key.startswith("enc:"):
        try:
            key = security.decrypt(key[4:])
        except Exception:
            key = ""
    return base, key, rows.get("ai_model") or "gpt-4o-mini"


@bp.post("/api/ai/captions")
def captions():
    import requests

    body = request.get_json(force=True, silent=True) or {}
    topic = (body.get("topic") or "").strip()
    try:
        count = min(10, max(1, int(body.get("count") or 5)))
    except (ValueError, TypeError):
        count = 5
    if not topic:
        return err("Topic required")
    base, key, model = ai_config()
    if not key:
        return err("AI API key not set — add it in Settings")
    try:
        r = requests.post(
            f"{base}/chat/completions", timeout=60,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.9,
                "messages": [
                    {"role": "system",
                     "content": ("You write short punchy Facebook reel captions, "
                                 "each with 3-6 relevant hashtags. Separate "
                                 "captions with a blank line. No quotes.")},
                    {"role": "user",
                     "content": f"Write {count} distinct captions about: {topic}"},
                ]})
        d = r.json()
        text = d["choices"][0]["message"]["content"]
        caps = [c.strip() for c in text.split("\n\n") if c.strip()]
        if len(caps) < 2:
            caps = [c.strip(" -\u2022\t") for c in text.split("\n")
                    if len(c.strip()) > 10]
        caps = [c for c in caps if c][:count]
        if not caps:
            return err("AI returned no captions")
        return ok({"captions": caps})
    except Exception as e:
        return err(f"AI request failed: {e}"[:200])

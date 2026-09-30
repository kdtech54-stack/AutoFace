"""Simple key/value settings API + settings page."""
from flask import Blueprint, render_template, request
from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Setting
from pagepilot.utils import security

bp = Blueprint("settings", __name__)


@bp.get("/settings")
def page():
    return render_template("settings.html", active_page="settings",
                           title="Settings")


@bp.get("/api/settings")
def list_settings():
    s = get_session()
    try:
        return ok({r.key: r.value for r in s.query(Setting).all()})
    finally:
        s.close()


@bp.post("/api/settings")
def save_settings():
    body = request.get_json(force=True, silent=True) or {}
    s = get_session()
    try:
        for k, v in body.items():
            v = str(v)
            # AI key is stored encrypted at rest
            if k == "ai_api_key" and v and not v.startswith("enc:"):
                v = "enc:" + security.encrypt(v)
            row = s.query(Setting).filter_by(key=str(k)).first()
            if row:
                row.value = v
            else:
                s.add(Setting(key=str(k), value=v))
        s.commit()
        return ok({"saved": len(body)})
    finally:
        s.close()

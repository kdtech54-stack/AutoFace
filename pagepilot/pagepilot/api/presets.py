"""Content Presets: page + CRUD / spintax test / media / caption APIs."""
import hashlib
import os
import shutil
import uuid

from flask import Blueprint, render_template, request
from sqlalchemy import or_

import config
from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import ContentPreset, MediaAsset, Caption
from pagepilot.utils import spintax
from pagepilot.utils import macros

bp = Blueprint("presets", __name__)

VALID_TYPES = ("post", "reel", "comment")
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp",
                ".mp4", ".mov"}


@bp.get("/presets")
def page():
    return render_template("presets.html", active_page="presets",
                           title="Content Presets")


def _parse_captions(raw):
    """Accept a list of strings or one blank-line-separated string."""
    if raw is None:
        return []
    if isinstance(raw, str):
        blocks, cur = [], []
        for line in raw.split("\n"):
            if line.strip() == "":
                if cur:
                    blocks.append("\n".join(cur).strip())
                    cur = []
            else:
                cur.append(line)
        if cur:
            blocks.append("\n".join(cur).strip())
        return [b for b in blocks if b]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _counts(s, preset_id):
    media_count = s.query(MediaAsset).filter_by(preset_id=preset_id).count()
    caption_count = s.query(Caption).filter_by(preset_id=preset_id).count()
    return media_count, caption_count


def _with_preview(p, media_count, caption_count):
    d = p.to_dict(media_count=media_count, caption_count=caption_count)
    d["preview"] = spintax.preview(p.template or "")
    return d


@bp.get("/api/presets")
def list_presets():
    ptype = (request.args.get("type") or "").strip().lower()
    q = (request.args.get("q") or "").strip()
    s = get_session()
    try:
        query = s.query(ContentPreset).order_by(ContentPreset.created_at.desc())
        if ptype in VALID_TYPES:
            query = query.filter(ContentPreset.type == ptype)
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            query = query.filter(or_(
                ContentPreset.title.ilike(like),
                ContentPreset.category.ilike(like),
                ContentPreset.template.ilike(like)))
        items = []
        for p in query.all():
            mc, cc = _counts(s, p.id)
            items.append(_with_preview(p, mc, cc))
        cats = sorted(r[0] for r in
                      s.query(ContentPreset.category).distinct().all())
        return ok({"presets": items, "categories": cats})
    finally:
        s.close()


@bp.get("/api/presets/<int:pid>")
def get_preset(pid):
    s = get_session()
    try:
        p = s.query(ContentPreset).filter_by(id=pid).first()
        if not p:
            return err("Preset not found", 404)
        media = [a.to_dict() for a in
                 s.query(MediaAsset).filter_by(preset_id=pid).all()]
        captions = [c.to_dict() for c in
                    s.query(Caption).filter_by(preset_id=pid)
                    .order_by(Caption.sort_order).all()]
        d = _with_preview(p, len(media), len(captions))
        d["media"] = media
        d["captions"] = captions
        return ok(d)
    finally:
        s.close()


@bp.post("/api/presets")
def create_preset():
    body = request.get_json(force=True, silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return err("Title is required")
    ptype = (body.get("type") or "post").strip().lower()
    if ptype not in VALID_TYPES:
        return err("Invalid preset type")
    category = (body.get("category") or "Default").strip() or "Default"
    template = body.get("template") or ""
    captions = _parse_captions(body.get("captions"))
    s = get_session()
    try:
        p = ContentPreset(title=title, type=ptype,
                          category=category, template=template)
        s.add(p)
        s.flush()
        for i, text in enumerate(captions):
            s.add(Caption(preset_id=p.id, text=text, sort_order=i))
        s.commit()
        return ok(_with_preview(p, 0, len(captions)))
    finally:
        s.close()


@bp.put("/api/presets/<int:pid>")
def update_preset(pid):
    body = request.get_json(force=True, silent=True) or {}
    s = get_session()
    try:
        p = s.query(ContentPreset).filter_by(id=pid).first()
        if not p:
            return err("Preset not found", 404)
        if "title" in body:
            title = (body.get("title") or "").strip()
            if not title:
                return err("Title is required")
            p.title = title
        if "type" in body:
            ptype = (body.get("type") or "").strip().lower()
            if ptype not in VALID_TYPES:
                return err("Invalid preset type")
            p.type = ptype
        if "category" in body:
            p.category = (body.get("category") or "Default").strip() or "Default"
        if "template" in body:
            p.template = body.get("template") or ""
        if "captions" in body:
            s.query(Caption).filter_by(preset_id=pid).delete()
            for i, text in enumerate(_parse_captions(body.get("captions"))):
                s.add(Caption(preset_id=pid, text=text, sort_order=i))
        s.commit()
        mc, cc = _counts(s, pid)
        return ok(_with_preview(p, mc, cc))
    finally:
        s.close()


@bp.delete("/api/presets")
def delete_presets():
    body = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in (body.get("ids") or []) if str(i).isdigit()]
    s = get_session()
    try:
        for pid in ids:
            p = s.query(ContentPreset).filter_by(id=pid).first()
            if not p:
                continue
            s.query(Caption).filter_by(preset_id=pid).delete()
            s.query(MediaAsset).filter_by(preset_id=pid).delete()
            s.delete(p)
            pdir = os.path.join(config.MEDIA_DIR, str(pid))
            if os.path.isdir(pdir):
                shutil.rmtree(pdir, ignore_errors=True)
        s.commit()
        return ok({"deleted": len(ids)})
    finally:
        s.close()


@bp.post("/api/presets/test-spin")
def test_spin():
    body = request.get_json(force=True, silent=True) or {}
    template = body.get("template") or ""
    if not template.strip():
        return err("Template is empty")
    return ok({"variants": spintax.variants(template, 5),
               "rendered": macros.render(template)})


@bp.post("/api/presets/<int:pid>/media")
def upload_media(pid):
    s = get_session()
    try:
        p = s.query(ContentPreset).filter_by(id=pid).first()
        if not p:
            return err("Preset not found", 404)
        files = request.files.getlist("files")
        if not files:
            return err("No files received")
        pdir = os.path.join(config.MEDIA_DIR, str(pid))
        os.makedirs(pdir, exist_ok=True)
        saved = []
        for f in files:
            if not f or not f.filename:
                continue
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in ALLOWED_EXTS:
                continue
            data = f.read()
            if not data:
                continue
            fname = uuid.uuid4().hex + ext
            fpath = os.path.join(pdir, fname)
            with open(fpath, "wb") as fh:
                fh.write(data)
            asset = MediaAsset(preset_id=pid, filename=f.filename,
                               filepath=fpath, filetype=ext.lstrip("."),
                               size_bytes=len(data),
                               sha256=hashlib.sha256(data).hexdigest())
            s.add(asset)
            s.flush()
            saved.append(asset.to_dict())
        s.commit()
        return ok({"uploaded": saved})
    finally:
        s.close()


@bp.delete("/api/presets/<int:pid>/media/<int:mid>")
def delete_media(pid, mid):
    s = get_session()
    try:
        a = s.query(MediaAsset).filter_by(id=mid, preset_id=pid).first()
        if not a:
            return err("Media not found", 404)
        try:
            if a.filepath and os.path.isfile(a.filepath):
                os.remove(a.filepath)
        except OSError:
            pass
        s.delete(a)
        s.commit()
        return ok({"deleted": mid})
    finally:
        s.close()

"""Pages & Groups: page route + pages / page-categories APIs.

Real Facebook page fetching needs the Playwright automation engine, so
POST /api/pages/fetch honestly returns {"ok": false, "error": "engine_pending"}.
Manual page add, categories, bulk category change and delete are fully working.
"""
from flask import Blueprint, render_template, request

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Account, Page, PageCategory, TaskItem, ActivityLog

bp = Blueprint("pages", __name__)


def _body():
    return request.get_json(silent=True) or {}


@bp.get("/pages")
def page():
    return render_template("pages.html", active_page="pages",
                           title="Pages & Groups")


@bp.get("/api/pages")
def list_pages():
    s = get_session()
    try:
        q = request.args.get("q", "").strip()
        account_id = request.args.get("account_id", type=int)
        category_id = request.args.get("category_id", type=int)
        query = s.query(Page).order_by(Page.id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Page.name.ilike(like)) | (Page.slug.ilike(like)) |
                (Page.page_uid.ilike(like)))
        if account_id:
            query = query.filter(Page.account_id == account_id)
        if category_id:
            query = query.filter(Page.category_id == category_id)
        pages = query.all()

        acc_map = {a.id: (a.display_name or a.username or a.uid or f"#{a.id}")
                   for a in s.query(Account).all()}
        cat_map = {c.id: c.name for c in s.query(PageCategory).all()}

        items = []
        for p in pages:
            d = p.to_dict()
            d["account"] = acc_map.get(p.account_id, "—")
            d["category"] = cat_map.get(p.category_id, "Default")
            items.append(d)

        account_opts = [{"id": i, "label": label}
                        for i, label in sorted(acc_map.items(),
                                               key=lambda kv: kv[1].lower())]
        categories = [c.to_dict()
                      for c in s.query(PageCategory).order_by(PageCategory.name).all()]
        return ok({"pages": items, "accounts": account_opts,
                   "categories": categories})
    finally:
        s.close()


@bp.post("/api/pages")
def add_page():
    s = get_session()
    try:
        b = _body()
        name = (b.get("name") or "").strip()
        if not name:
            return err("Page name is required")
        account_id = b.get("account_id")
        if account_id is not None:
            if not s.query(Account).filter_by(id=account_id).first():
                return err("Account not found")
        category_id = b.get("category_id")
        if category_id is not None:
            if not s.query(PageCategory).filter_by(id=category_id).first():
                return err("Category not found")
        page = Page(account_id=account_id, name=name,
                    page_uid=(b.get("page_uid") or "").strip(),
                    slug=(b.get("slug") or "").strip(),
                    url=(b.get("url") or "").strip(),
                    category_id=category_id, status="active")
        s.add(page)
        s.flush()
        s.add(ActivityLog(account_id=account_id, page_id=page.id,
                          action="page_fetch", status="info",
                          message=f"Page added manually: {name}"))
        s.commit()
        return ok(page.to_dict())
    finally:
        s.close()


@bp.post("/api/pages/fetch")
def fetch_pages():
    data = _body()
    ids = data.get("account_ids", "all")
    try:
        from pagepilot.automation.pages_fetch import fetch_many
        from pagepilot.automation.browser import engine_available
    except Exception:
        return err("engine_pending")
    if not engine_available():
        return err("engine_pending")
    s = get_session()
    try:
        q = s.query(Account.id)
        if ids != "all":
            try:
                id_list = [int(i) for i in (ids or [])]
            except (ValueError, TypeError):
                return err("Invalid ids")
            q = q.filter(Account.id.in_(id_list))
        id_list = [r[0] for r in q.all()]
    finally:
        s.close()
    if not id_list:
        return err("No accounts selected")
    return ok(fetch_many(id_list))


@bp.put("/api/pages/category")
def bulk_category():
    s = get_session()
    try:
        b = _body()
        ids = b.get("ids") or []
        category_id = b.get("category_id")  # None = unassign
        if not ids:
            return err("No pages selected")
        if category_id is not None:
            if not s.query(PageCategory).filter_by(id=category_id).first():
                return err("Category not found")
        n = (s.query(Page).filter(Page.id.in_(ids))
             .update({"category_id": category_id}, synchronize_session=False))
        s.commit()
        return ok({"updated": n})
    finally:
        s.close()


@bp.delete("/api/pages")
def delete_pages():
    s = get_session()
    try:
        ids = _body().get("ids") or []
        if not ids:
            return err("No pages selected")
        s.query(TaskItem).filter(TaskItem.page_id.in_(ids)).delete(
            synchronize_session=False)
        n = (s.query(Page).filter(Page.id.in_(ids))
             .delete(synchronize_session=False))
        s.commit()
        return ok({"deleted": n})
    finally:
        s.close()


@bp.get("/api/page-categories")
def list_categories():
    s = get_session()
    try:
        cats = s.query(PageCategory).order_by(PageCategory.name).all()
        out = []
        for c in cats:
            d = c.to_dict()
            d["pages"] = s.query(Page).filter_by(category_id=c.id).count()
            out.append(d)
        unassigned = s.query(Page).filter(Page.category_id.is_(None)).count()
        return ok({"categories": out, "unassigned": unassigned})
    finally:
        s.close()


@bp.post("/api/page-categories")
def add_category():
    s = get_session()
    try:
        name = (_body().get("name") or "").strip()
        if not name:
            return err("Category name is required")
        if s.query(PageCategory).filter_by(name=name).first():
            return err("Category already exists")
        c = PageCategory(name=name)
        s.add(c)
        s.commit()
        return ok(c.to_dict())
    finally:
        s.close()


@bp.delete("/api/page-categories")
def delete_category():
    s = get_session()
    try:
        cid = _body().get("id")
        cat = s.query(PageCategory).filter_by(id=cid).first()
        if not cat:
            return err("Category not found")
        (s.query(Page).filter_by(category_id=cid)
         .update({"category_id": None}, synchronize_session=False))
        s.delete(cat)
        s.commit()
        return ok({"deleted": cid})
    finally:
        s.close()

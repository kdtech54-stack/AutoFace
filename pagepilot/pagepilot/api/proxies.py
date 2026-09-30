"""Proxy Management: page + proxy/group CRUD / bulk import / check APIs."""
import re
from datetime import datetime

from flask import Blueprint, render_template, request
from sqlalchemy import func

from pagepilot.api import ok, err
from pagepilot.database import get_session
from pagepilot.models import Proxy, ProxyGroup, Account
from pagepilot.utils import security

bp = Blueprint("proxies", __name__)

VALID_PROTOCOLS = ("http", "socks4", "socks5")
VALID_STATUSES = ("unknown", "active", "dead")
_SCHEME_RE = re.compile(r"^(socks5|socks4|https?)://(.+)$", re.I)


@bp.get("/proxies")
def page():
    return render_template("proxies.html", active_page="proxies",
                           title="Proxy Management")


def parse_proxy_line(line, default_protocol="http"):
    """Auto-detect one proxy line.

    Accepted: host:port | host:port:user:pass |
              socks5://host:port | socks5://host:port:user:pass |
              socks4://... | http(s)://...
    Returns dict or None when the line is blank, a comment, or invalid.
    """
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    proto = (default_protocol or "http").lower()
    rest = line
    m = _SCHEME_RE.match(line)
    if m:
        proto = m.group(1).lower()
        rest = m.group(2).strip()
    if proto not in VALID_PROTOCOLS:
        return None
    parts = rest.split(":")
    if len(parts) == 2:
        host, port, user, pw = parts[0], parts[1], "", ""
    elif len(parts) >= 4:
        host, port, user = parts[0], parts[1], parts[2]
        pw = ":".join(parts[3:])
    else:
        return None
    host = host.strip()
    if not host:
        return None
    try:
        port_n = int(port.strip())
    except (ValueError, AttributeError):
        return None
    if not 1 <= port_n <= 65535:
        return None
    return {"host": host, "port": port_n, "protocol": proto,
            "username": user or "", "password": pw or ""}


@bp.get("/api/proxies")
def list_proxies():
    q = (request.args.get("q") or "").strip()
    group_id = request.args.get("group_id") or ""
    status = (request.args.get("status") or "").strip().lower()
    s = get_session()
    try:
        query = s.query(Proxy).order_by(Proxy.id)
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            query = query.filter(Proxy.host.ilike(like))
        if group_id.isdigit():
            query = query.filter(Proxy.group_id == int(group_id))
        if status in VALID_STATUSES:
            query = query.filter(Proxy.status == status)
        proxies = query.all()
        counts = {}
        if proxies:
            pids = [p.id for p in proxies]
            rows = (s.query(Account.proxy_id, func.count(Account.id))
                    .filter(Account.proxy_id.in_(pids))
                    .group_by(Account.proxy_id).all())
            counts = {pid: c for pid, c in rows}
        groups = {g.id: g.name for g in s.query(ProxyGroup).all()}
        items = []
        for p in proxies:
            d = p.to_dict(profiles=counts.get(p.id, 0))
            d["group"] = groups.get(p.group_id, "")
            items.append(d)
        return ok({
            "proxies": items,
            "groups": [g.to_dict() for g in
                       s.query(ProxyGroup).order_by(ProxyGroup.name).all()],
        })
    finally:
        s.close()


@bp.post("/api/proxies/import")
def import_proxies():
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text") or ""
    protocol = (body.get("protocol") or "http").strip().lower()
    if protocol not in VALID_PROTOCOLS:
        protocol = "http"
    group_id = body.get("group_id")
    s = get_session()
    try:
        group = None
        if group_id and str(group_id).isdigit():
            group = s.query(ProxyGroup).filter_by(id=int(group_id)).first()
        seen = {(p.host.lower(), p.port) for p in s.query(Proxy).all()}
        imported, skipped, invalid = 0, 0, 0
        for line in text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            parsed = parse_proxy_line(line, protocol)
            if not parsed:
                invalid += 1
                continue
            key = (parsed["host"].lower(), parsed["port"])
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            s.add(Proxy(
                host=parsed["host"], port=parsed["port"],
                protocol=parsed["protocol"],
                username_enc=security.encrypt(parsed["username"])
                if parsed["username"] else "",
                password_enc=security.encrypt(parsed["password"])
                if parsed["password"] else "",
                group_id=group.id if group else None,
                status="unknown"))
            imported += 1
        s.commit()
        return ok({"imported": imported,
                   "skipped": skipped + invalid, "invalid": invalid})
    finally:
        s.close()


@bp.delete("/api/proxies")
def delete_proxies():
    body = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in (body.get("ids") or []) if str(i).isdigit()]
    s = get_session()
    try:
        if ids:
            s.query(Account).filter(Account.proxy_id.in_(ids)).update(
                {"proxy_id": None}, synchronize_session=False)
            s.query(Proxy).filter(Proxy.id.in_(ids)).delete(
                synchronize_session=False)
            s.commit()
        return ok({"deleted": len(ids)})
    finally:
        s.close()


@bp.post("/api/proxies/check")
def check_proxies():
    """Real proxy test: route an IP-lookup request through each proxy and
    record status, latency and geo location. No browser needed."""
    import time

    import requests

    body = request.get_json(force=True, silent=True) or {}
    ids = body.get("ids", "all")
    s = get_session()
    try:
        q = s.query(Proxy)
        if ids != "all":
            id_list = [int(i) for i in (ids or []) if str(i).isdigit()]
            q = q.filter(Proxy.id.in_(id_list))
        proxies = q.all()
        results = []
        for p in proxies:
            res = _test_proxy(p, requests, time)
            p.status = res["status"]
            p.latency_ms = res.get("latency_ms")
            p.location = res.get("location", "")
            p.timezone_name = res.get("timezone", "")
            p.last_check = datetime.utcnow()
            results.append({"id": p.id, **res})
        s.commit()
        return ok(results)
    finally:
        s.close()


def _test_proxy(p, requests, time) -> dict:
    scheme = {"http": "http", "socks4": "socks4",
              "socks5": "socks5"}.get(p.protocol, "http")
    cred = ""
    u = security.decrypt(p.username_enc)
    pw = security.decrypt(p.password_enc)
    if u:
        cred = f"{u}:{pw}@"
    proxy_url = f"{scheme}://{cred}{p.host}:{p.port}"
    proxies = {"http": proxy_url, "https": proxy_url}
    t0 = time.time()
    try:
        r = requests.get(
            "http://ip-api.com/json/?fields=status,country,regionName,city,timezone,query",
            proxies=proxies, timeout=20)
        ms = int((time.time() - t0) * 1000)
        d = r.json()
        if d.get("status") == "success":
            loc = ", ".join(x for x in
                            [d.get("city"), d.get("regionName"),
                             d.get("country")] if x)
            return {"status": "active", "latency_ms": ms,
                    "location": loc, "timezone": d.get("timezone", ""),
                    "ip": d.get("query", "")}
        return {"status": "dead", "latency_ms": ms}
    except Exception as e:
        return {"status": "dead", "latency_ms": None,
                "error": str(e)[:120]}


@bp.get("/api/proxy-groups")
def list_groups():
    s = get_session()
    try:
        return ok([g.to_dict() for g in
                   s.query(ProxyGroup).order_by(ProxyGroup.name).all()])
    finally:
        s.close()


@bp.post("/api/proxy-groups")
def create_group():
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return err("Group name is required")
    s = get_session()
    try:
        if s.query(ProxyGroup).filter_by(name=name).first():
            return err("Group already exists")
        g = ProxyGroup(name=name)
        s.add(g)
        s.commit()
        return ok(g.to_dict())
    finally:
        s.close()


@bp.delete("/api/proxy-groups")
def delete_groups():
    body = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in (body.get("ids") or []) if str(i).isdigit()]
    s = get_session()
    try:
        if ids:
            s.query(Proxy).filter(Proxy.group_id.in_(ids)).update(
                {"group_id": None}, synchronize_session=False)
            s.query(ProxyGroup).filter(ProxyGroup.id.in_(ids)).delete(
                synchronize_session=False)
            s.commit()
        return ok({"deleted": len(ids)})
    finally:
        s.close()

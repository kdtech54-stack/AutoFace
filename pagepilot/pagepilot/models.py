"""PagePilot data model. Scalar-only to_dict() helpers (no lazy loads)."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (String, Integer, Text, DateTime, Boolean,
                        ForeignKey)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


DEFAULT_SETTINGS = {
    "min_spacing": "3",
    "max_spacing": "10",
    "switch_on_errors": "10",
    "scheduler_enabled": "0",
}


class AccountCategory(Base):
    __tablename__ = "account_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), index=True, default="")
    username: Mapped[str] = mapped_column(String(128), default="")
    display_name: Mapped[str] = mapped_column(String(128), default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    twofa_enc: Mapped[str] = mapped_column(Text, default="")
    cookies_enc: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_categories.id"), nullable=True)
    tags: Mapped[str] = mapped_column(String(255), default="")
    proxy_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxies.id"), nullable=True)
    # unknown | live | logged_in | checkpoint | dead
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "uid": self.uid, "username": self.username,
                "display_name": self.display_name, "category_id": self.category_id,
                "tags": self.tags, "proxy_id": self.proxy_id, "status": self.status,
                "last_check": self.last_check.isoformat() if self.last_check else None,
                "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class PageCategory(Base):
    __tablename__ = "page_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Page(Base):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True)
    page_uid: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(160), default="")
    slug: Mapped[str] = mapped_column(String(160), default="")
    url: Mapped[str] = mapped_column(String(255), default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("page_categories.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self):
        return {"id": self.id, "account_id": self.account_id,
                "page_uid": self.page_uid, "name": self.name,
                "slug": self.slug, "url": self.url,
                "category_id": self.category_id, "status": self.status,
                "followers": self.followers,
                "last_sync": self.last_sync.isoformat() if self.last_sync else None}


class ContentPreset(Base):
    __tablename__ = "content_presets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    # post | reel | comment
    type: Mapped[str] = mapped_column(String(16), default="post")
    category: Mapped[str] = mapped_column(String(80), default="Default")
    template: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self, media_count=0, caption_count=0):
        return {"id": self.id, "title": self.title, "type": self.type,
                "category": self.category, "template": self.template,
                "media_count": media_count, "caption_count": caption_count,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    preset_id: Mapped[int] = mapped_column(ForeignKey("content_presets.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    filepath: Mapped[str] = mapped_column(String(512))
    filetype: Mapped[str] = mapped_column(String(16), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)

    def to_dict(self):
        return {"id": self.id, "preset_id": self.preset_id,
                "filename": self.filename, "filetype": self.filetype,
                "size_bytes": self.size_bytes, "sha256": self.sha256}


class Caption(Base):
    __tablename__ = "captions"
    id: Mapped[int] = mapped_column(primary_key=True)
    preset_id: Mapped[int] = mapped_column(ForeignKey("content_presets.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "preset_id": self.preset_id,
                "text": self.text, "sort_order": self.sort_order}


class ProxyGroup(Base):
    __tablename__ = "proxy_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Proxy(Base):
    __tablename__ = "proxies"
    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=8080)
    username_enc: Mapped[str] = mapped_column(Text, default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    # http | socks4 | socks5
    protocol: Mapped[str] = mapped_column(String(16), default="http")
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("proxy_groups.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(128), default="")
    timezone_name: Mapped[str] = mapped_column(String(64), default="")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # unknown | active | dead
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self, profiles=0):
        return {"id": self.id, "host": self.host, "port": self.port,
                "protocol": self.protocol, "group_id": self.group_id,
                "location": self.location, "timezone": self.timezone_name,
                "latency_ms": self.latency_ms, "status": self.status,
                "profiles": profiles,
                "proxy": f"{self.protocol}://{self.host}:{self.port}",
                "last_check": self.last_check.isoformat() if self.last_check else None}


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    # reel_post | post
    kind: Mapped[str] = mapped_column(String(32), default="reel_post")
    # idle | running | paused | done
    status: Mapped[str] = mapped_column(String(32), default="idle")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "status": self.status, "config": self.config_json,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class TaskItem(Base):
    __tablename__ = "task_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id"), nullable=True)
    # direct account target (warm-up tasks); null for page-based items
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True)
    preset_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_presets.id"), nullable=True)
    # queued | running | done | failed | skipped
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id,
                "page_id": self.page_id, "account_id": self.account_id,
                "preset_id": self.preset_id,
                "status": self.status, "attempts": self.attempts,
                "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
                "executed_at": self.executed_at.isoformat() if self.executed_at else None,
                "result": self.result_json}


class PostedHash(Base):
    """Duplicate guard: every published media's sha256 per page."""
    __tablename__ = "posted_hashes"
    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id"), nullable=True, index=True)
    preset_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_presets.id"), nullable=True)
    media_path: Mapped[str] = mapped_column(String(512), default="")
    posted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True)


class RepliedComment(Base):
    """Comments we've already replied to (never reply twice)."""
    __tablename__ = "replied_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"), index=True)
    comment_key: Mapped[str] = mapped_column(String(64), index=True)
    replied_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True)
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id"), nullable=True)
    # reel_published | post_published | login | live_check | page_fetch | ...
    action: Mapped[str] = mapped_column(String(80), index=True)
    # ok | failed | info
    status: Mapped[str] = mapped_column(String(32), default="info")
    message: Mapped[str] = mapped_column(Text, default="")

    def to_dict(self, account_name="", page_name=""):
        return {"id": self.id,
                "ts": self.ts.isoformat() if self.ts else None,
                "account_id": self.account_id, "page_id": self.page_id,
                "account": account_name, "page": page_name,
                "action": self.action, "status": self.status,
                "message": self.message}


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True)
    cron_expr: Mapped[str] = mapped_column(String(64), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "task_id": self.task_id,
                "cron": self.cron_expr, "enabled": self.enabled,
                "next_run": self.next_run.isoformat() if self.next_run else None}


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")

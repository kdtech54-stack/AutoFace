"""SQLite engine + session factory + DB bootstrap with seed data."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from .models import (Base, AccountCategory, PageCategory, ProxyGroup,
                     Setting, DEFAULT_SETTINGS)

os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
engine = create_engine(f"sqlite:///{config.DB_PATH}",
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    return SessionLocal()


def init_db():
    Base.metadata.create_all(engine)
    s = SessionLocal()
    try:
        if s.query(AccountCategory).count() == 0:
            s.add(AccountCategory(name="General"))
        if s.query(PageCategory).count() == 0:
            s.add(PageCategory(name="Default"))
        if s.query(ProxyGroup).count() == 0:
            s.add(ProxyGroup(name="Default"))
        for k, v in DEFAULT_SETTINGS.items():
            if s.query(Setting).filter_by(key=k).count() == 0:
                s.add(Setting(key=k, value=v))
        s.commit()
    finally:
        s.close()

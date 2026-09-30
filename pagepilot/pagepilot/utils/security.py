"""Fernet encryption for stored credentials. Key lives in DATA_DIR/.key."""
import os
from cryptography.fernet import Fernet

import config

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if os.path.exists(config.KEY_PATH):
            with open(config.KEY_PATH, "rb") as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key()
            with open(config.KEY_PATH, "wb") as f:
                f.write(key)
            try:
                os.chmod(config.KEY_PATH, 0o600)
            except OSError:
                pass
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return ""

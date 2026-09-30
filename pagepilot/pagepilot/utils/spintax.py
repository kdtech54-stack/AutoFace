"""Spintax engine: {option1|option2|option3} with nesting support."""
import random
import re

_PATTERN = re.compile(r"\{([^{}]*)\}")


def spin(text: str, _depth: int = 0) -> str:
    """Return one random spin of the template."""
    if not text or _depth > 10:
        return text or ""

    def _repl(m):
        opts = m.group(1).split("|")
        return random.choice(opts) if opts else ""

    new = _PATTERN.sub(_repl, text)
    return spin(new, _depth + 1) if new != text else new


def variants(text: str, n: int = 5) -> list:
    """Return n random spins (may contain duplicates for small option sets)."""
    return [spin(text) for _ in range(n)]


def preview(text: str) -> str:
    """A short preview: first spin, truncated."""
    s = spin(text)
    return s if len(s) <= 90 else s[:87] + "..."

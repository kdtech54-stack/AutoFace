"""Dynamic macros: $number $timespan $time $date $text $smile."""
import random
import time
from datetime import datetime

_SMILES = ["😂", "🔥", "❤️", "👍", "😍", "🙌", "💯", "✨", "🎉", "😎",
           "🤣", "👏", "💥", "🌟"]
_WORDS = ["amazing", "incredible", "viral", "trending", "epic", "wild",
          "funny", "awesome", "unbelievable", "crazy"]


def apply_macros(text: str) -> str:
    now = datetime.now()
    repl = {
        "$number": str(random.randint(1000, 9999)),
        "$timespan": str(int(time.time())),
        "$time": now.strftime("%H:%M"),
        "$date": now.strftime("%Y-%m-%d"),
        "$smile": random.choice(_SMILES),
        "$text": random.choice(_WORDS),
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text


def render(template: str) -> str:
    """Apply macros first, then spintax — one fully rendered caption."""
    try:
        from .spintax import spin
    except ImportError:  # standalone script use
        from spintax import spin
    return spin(apply_macros(template or ""))

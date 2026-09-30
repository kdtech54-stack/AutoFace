"""PagePilot automation engine (Playwright).

Runs on the user's Windows machine against their own Facebook accounts.
Each account gets an isolated persistent browser profile + its assigned proxy.
"""
from .browser import new_context, proxy_config_for  # noqa: F401
from .checker import check_account, check_many  # noqa: F401
from .pages_fetch import fetch_pages_for_account, fetch_many  # noqa: F401
from .poster import publish_reel, publish_post  # noqa: F401
from .worker import (start as worker_start, stop as worker_stop,  # noqa: F401
                     is_running as worker_running)

ENGINE_VERSION = "0.1.0"

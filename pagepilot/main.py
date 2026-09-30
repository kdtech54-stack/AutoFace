"""PagePilot entry point.

Runs the local Flask server in a background thread and opens the
desktop window with pywebview. Use --server-only to run just the
web server (handy for development / smoke tests).
"""
import os
import sys
import threading

# Self-contained Playwright browsers: the Windows build bundles Chromium
# next to the app; point Playwright at it before anything imports it.
if getattr(sys, "frozen", False):
    _pw = os.path.join(getattr(sys, "_MEIPASS", ""), "pw-browsers")
    if os.path.isdir(_pw):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _pw)

import config
from pagepilot import create_app
from pagepilot.database import init_db


def run_server():
    app = create_app()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT,
            debug=False, use_reloader=False)


def main():
    init_db()
    if "--server-only" in sys.argv:
        run_server()
        return
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    import webview
    webview.create_window(
        config.APP_NAME,
        f"http://{config.FLASK_HOST}:{config.FLASK_PORT}/",
        width=1440, height=900, min_size=(1100, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()

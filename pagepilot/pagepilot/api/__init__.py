"""Dynamic blueprint loader.

Each module in MANIFEST may expose a Flask Blueprint named `bp`.
Missing modules are skipped silently so the app boots even while
some modules are still being built.
"""
import importlib

MANIFEST = [
    "pagepilot.api.dashboard",
    "pagepilot.api.accounts",
    "pagepilot.api.pages",
    "pagepilot.api.presets",
    "pagepilot.api.proxies",
    "pagepilot.api.posting",
    "pagepilot.api.scheduler",
    "pagepilot.api.settings",
    "pagepilot.api.ai",
    "pagepilot.api.engagement",
]


def load_blueprints(app):
    for mod_name in MANIFEST:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            app.logger.warning("module not ready yet: %s", mod_name)
            continue
        bp = getattr(mod, "bp", None)
        if bp is not None:
            app.register_blueprint(bp)
        else:
            app.logger.warning("no `bp` in %s", mod_name)


def ok(data=None):
    from flask import jsonify
    return jsonify({"ok": True, "data": data})


def err(message, code=400):
    from flask import jsonify
    return jsonify({"ok": False, "error": message}), code

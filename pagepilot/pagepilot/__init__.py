"""PagePilot Flask application factory."""
from flask import Flask, redirect


def create_app():
    app = Flask(__name__,
                template_folder="ui/templates",
                static_folder="ui/static")
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB uploads

    from .api import load_blueprints
    load_blueprints(app)

    @app.get("/")
    def index():
        return redirect("/dashboard")

    return app

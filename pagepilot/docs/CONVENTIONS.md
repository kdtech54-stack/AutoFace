# PagePilot module conventions

Every screen is built by exactly one owner. Do not edit files owned by another
module. Shared foundation files (`models.py`, `database.py`, `__init__.py`,
`base.html`, `style.css`, `app.js`, utils) are already written — read them,
do not rewrite them.

## File ownership per module

| Module   | API file                | Template                          | JS                              |
|----------|-------------------------|-----------------------------------|---------------------------------|
| accounts | `pagepilot/api/accounts.py` | `pagepilot/ui/templates/accounts.html` | `pagepilot/ui/static/js/accounts.js` |
| pages    | `pagepilot/api/pages.py`    | `pagepilot/ui/templates/pages.html`    | `pagepilot/ui/static/js/pages.js`    |
| presets  | `pagepilot/api/presets.py`  | `pagepilot/ui/templates/presets.html`  | `pagepilot/ui/static/js/presets.js`  |
| proxies  | `pagepilot/api/proxies.py`  | `pagepilot/ui/templates/proxies.html`  | `pagepilot/ui/static/js/proxies.js`  |
| posting  | `pagepilot/api/posting.py`  | `pagepilot/ui/templates/posting.html`  | `pagepilot/ui/static/js/posting.js`  |

## Rules

1. **Blueprint**: each API file exposes `bp = Blueprint("<name>", __name__)` with
   NO `url_prefix`. Page route: `@bp.get("/accounts")` etc. API routes:
   `@bp.get("/api/accounts")` etc. The app auto-loads `bp` from
   `pagepilot/api/__init__.py` MANIFEST.
2. **Responses**: always `{"ok": true, "data": ...}` or `{"ok": false, "error": "..."}`.
   Use `from pagepilot.api import ok, err`.
3. **DB**: `from pagepilot.database import get_session`; open session, `try/finally: s.close()`.
   Models have scalar-only `.to_dict()`.
4. **Secrets**: passwords / 2FA / cookies / proxy creds go through
   `pagepilot.utils.security.encrypt/decrypt`. Never return decrypted secrets in API output.
5. **Templates**: `{% extends "base.html" %}`, put page JS via
   `{% block scripts %}<script src="{{ url_for('static', filename='js/accounts.js') }}"></script>{% endblock %}`.
   Render with `render_template("accounts.html", active_page="accounts", title="Accounts")`.
   Reuse CSS classes from `style.css` (card, btn, table, badge, modal, tabs, toolbar, input...).
   Reuse JS helpers from `app.js`: `api()`, `el()`, `esc()`, `toast()`, `statusBadge()`,
   `openModal()/closeModal()`, `confirmDialog()`, `fmtDT()`.
6. **Honesty**: never fake live data. Anything needing the Playwright automation
   engine (real FB login check, real page fetch, real publish) must call its endpoint
   and show a clear toast like "Automation engine milestone me aayega" if the
   endpoint returns `{"ok": false, "error": "engine_pending"}`. CRUD, import parsing,
   spintax/macros, file uploads must be fully working now.
7. **No new pip dependencies.** Keep imports to stdlib + requirements.txt.
8. **Verify**: run `python -m py_compile` on every file you create. Report the result.

## Shared vocabulary (activity log actions)

`reel_published`, `post_published`, `login`, `live_check`, `page_fetch`,
`account_import`, `proxy_check`. Status: `ok` | `failed` | `info`.

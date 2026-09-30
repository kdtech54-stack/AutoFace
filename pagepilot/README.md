# PagePilot — Facebook Automation Suite (Windows)

A fully working desktop automation suite for managing Facebook accounts,
pages, content presets and proxies — with scheduled/auto reel & post publishing.

Inspired by the "KartStudio" tool; rebuilt from scratch with extra features.

## Status: feature-complete — pending first live Facebook validation on Windows

## Project layout

```
pagepilot/
  main.py                 # entry point (Flask server + pywebview window)
  config.py               # paths, ports, defaults
  requirements.txt
  build_local.bat         # backup: build the .exe on your own Windows PC
  .github/workflows/      # GitHub Actions: automatic Windows .exe builds
  pagepilot/
    __init__.py           # Flask app factory
    database.py           # SQLite engine + seed data
    models.py             # all DB tables
    utils/                # spintax, macros, credential encryption
    api/                  # one blueprint module per screen (dashboard, accounts, ...)
    ui/templates/         # Jinja2 pages (extend base.html)
    ui/static/            # css + js
```

## Run (development)

```
pip install -r requirements.txt
python main.py --server-only   # web UI at http://127.0.0.1:5057
python main.py                 # desktop window
```

## Build the Windows installer

The .exe is fully self-contained (Chromium bundled — the user's PC needs
no Python or Playwright installed).

**Option A — GitHub Actions (recommended):**
1. Create a new GitHub repo and push this folder to it.
2. Go to the repo's **Actions** tab → **Build Windows EXE** → **Run workflow**.
   (Or push a tag like `v1.0.0` — a Release is created automatically.)
3. Download `PagePilot-windows.zip` from the run's **Artifacts** (or from Releases).
4. Unzip on your Windows PC and run `PagePilot.exe`.

**Option B — local build:** on a Windows PC with Python 3.11+,
double-click `build_local.bat`, then run `dist\PagePilot\PagePilot.exe`.

## First-run checklist (important)

1. **Settings** → keep Headless ON for normal use; turn it OFF for a first
   login if Facebook shows a checkpoint (solve it in the visible window).
2. **Accounts** → bulk-import UID / password / 2FA / cookies. **Check Live**
   saves a real Facebook session per account (stored encrypted on your PC).
3. **Proxies** → import and assign proxies; one account = one proxy ideally.
4. **Pages** → Fetch Pages per account, then **Warm-up** new accounts
   (Comments & Engagement page) before heavy posting.
5. **Content Presets** → upload media, write captions with spintax `{a|b}`,
   macros `{page_name}` etc. Use ✨ AI Captions with your API key from Settings.
6. **Reel Post** → build a task; **Auto Page Scheduler** → set a schedule;
   press **Run** in the topbar to start the queue.
7. Safety is ON by default: video uniquifier + duplicate guard.

⚠️ Facebook can checkpoint or restrict accounts that automate too fast.
Start slow (10–15 sec spacing, a few posts/day per account), use warmed
sessions, and expect to tune selectors if Facebook changes its UI.

## Module contracts

See `docs/CONVENTIONS.md`.

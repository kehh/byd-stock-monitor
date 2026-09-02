# BYD Stock Monitor — History Logging & GitHub Deployment

- **Date:** 2026-09-02
- **Status:** Approved design

## Context

`monitor.py` already fetches the BYD Dealer Group inventory page
(`https://evdealergroup-byd.com.au/inventory?type=d`), parses vehicle cards,
prints a table of Atto 2 units by state/variant, and emails when new Dynamic
units appear in any Australian state.

The user wants:
1. A log of stock numbers **over time**, enough to visualise as a graph.
2. Dependencies managed with **uv**.
3. Deployment to **free hosting** (GitHub chosen).

Deployment decision (user-confirmed): **GitHub Actions** runs the monitor on a
cron schedule. Graph output (user-confirmed): **static PNG + GitHub Pages**.
Log granularity (user-confirmed): **both** per-state/per-variant counts AND the
full stock-number sets per poll.

## Design

### 1. History logging (`history.csv`)

One row per poll per (state, variant) group:

```
timestamp_utc,state,variant,count,stock_numbers
```

- `timestamp_utc` — `YYYY-MM-DD HH:MM:SS`, in UTC.
- `state` — `WA`, `VIC`, `NSW`, `QLD`, `SA`, `ACT`, `NT`, `TAS`.
- `variant` — `Dynamic`, `Premium`, `Demo` (if present).
- `count` — number of units in that group at that poll.
- `stock_numbers` — semicolon-separated stock numbers, empty if count is 0.

Rows are **appended** each run. A fresh run on a clean checkout appends a full
snapshot row-set; because the file is committed back after every run, state is
accumulated in the repo itself. No in-memory reconciliation needed for the
graph — the graph reads `history.csv` directly.

A `csv.DictWriter` writes the file with a header. If the file exists with a
different header on a fresh/legacy state, the writer appends matching the
existing header.

### 2. Graph generation (`graph.py`)

New module, run after each poll (and on demand). Reads `history.csv` and
produces:

- `graph.png` — a line chart, one line per (state, variant) series with data,
  showing unit count over time. Uses matplotlib with `Agg` backend (headless).
- `index.html` — a minimal self-contained page that embeds `graph.png`
  (`<img src="graph.png">`) plus a small table of current stock derived from
  the latest `history.csv` rows. This is what GitHub Pages serves at the repo
  root.

`graph.py` is idempotent: it overwrites `graph.png` and `index.html` each run.

### 3. Dependency management with uv

- Add `pyproject.toml` (uv-compatible), declared project `byd-stock-monitor`.
- Only runtime dependency: **matplotlib**.
- Everything else (fetch, parse, SMTP, JSON, CSV) stays in the Python stdlib.
- Local workflow: `uv sync`, then `uv run python monitor.py` and
  `uv run python graph.py`.

### 4. Deployment (GitHub Actions + GitHub Pages)

New public GitHub repo (suggested name `byd-stock-monitor`).

`.github/workflows/monitor.yml`:

- Triggers:
  - `schedule: cron '*/10' ` (every 10 minutes)
  - `workflow_dispatch` (manual)
- Steps:
  1. Check out repo (with fetch-depth to allow commit/push).
  2. Set up uv (`astral-sh/setup-uv`).
  3. `uv sync` (installs matplotlib).
  4. `uv run python monitor.py` — fetches, logs to `history.csv`, updates
     `state.json`, appends `notifications.log`, sends email if env configured.
  5. `uv run python graph.py` — regenerates `graph.png` + `index.html`.
  6. Commit and push `history.csv`, `state.json`, `notifications.log`,
     `graph.png`, `index.html` back to the repo (with the Actions bot user).
  7. GitHub Pages serves the repo root (`/`, branch `main`), so
     `https://<user>.github.io/byd-stock-monitor/` shows `index.html` with the
     graph.

Notes:
- When total inventory is large (~1.8 MB HTML), cadence of 10 minutes is fine
  for Actions' free tier (actions give 2,000 min/month; each run ~1 min).
- If the inventory fetch fails, the job logs the error and exits non-zero but
  still regenerates the graph from existing history and **does not** write a
  partial/corrupt row. Email errors are non-fatal (already the case).

### 5. Email

Unchanged behaviour. In GitHub Actions, credentials are stored as repository
secrets (`TO_EMAIL`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`) and exported into the
job environment. Absent secrets → email disabled (already the default).

### 6. README

Update README with:
- The `uv` commands.
- The GitHub Pages URL once the repo exists.
- Note that history accumulates in `history.csv` in the repo.

## Files affected

| File | Change |
|------|--------|
| `monitor.py` | Add history logging (append rows after parse). |
| `graph.py` | New — read `history.csv`, write `graph.png` + `index.html`. |
| `pyproject.toml` | New — uv project, matplotlib dep. |
| `.github/workflows/monitor.yml` | New — scheduled run + commit back. |
| `index.html`, `graph.png` | Generated output, committed. |
| `history.csv` | Generated time-series data, committed. |
| `.gitignore` | New — ignore `__pycache__/`, `.venv/`, local caches; keep data files. |
| `README.md` | Update run instructions, uv, Pages URL. |

## Out of scope / deferred

- Creating the GitHub repo and pushing (needs `gh auth login` by the user).
- Enabling GitHub Pages in repo settings (user action, or via API if authed).
- Sending email reliably in Actions requires the user to set repo secrets.

## Testing

- Local: install uv, `uv sync`, run `monitor.py` against live page (logs rows),
  run `graph.py` (produces PNG + HTML), inspect output.
- Parser already verified against live inventory (147 Atto 2 cards).
- Workflow file validated via `actionlint` if available, else manual review.
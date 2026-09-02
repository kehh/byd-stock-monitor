# BYD Stock Monitor

Monitors the EVDealer Group BYD inventory page for **all BYD models**
across **Australia (all states)**, recording stock by (state, model, variant,
colour). Emails are sent only for **Atto 2 Dynamic** units when credentials
are configured.

## How it works

The script fetches the server-rendered inventory page
(`https://evdealergroup-byd.com.au/inventory?type=d`), parses every vehicle
card, and records one history row per (state, model, variant, colour) cell.
All 12 models and 25 known paint colours are tracked. Newly-seen **Atto 2
Dynamic** units are logged to `notifications.log` and emailed if email is
enabled.

## Dependencies

You need two files and one tool:

- `monitor.py` — fetches inventory, parses cards, appends history, sends emails
- `graph.py` — renders `index.html` dashboard from history
- [uv](https://docs.astral.sh/uv/) — runs the scripts

```bash
uv sync
```

Then run:

```bash
uv run python monitor.py
uv run python graph.py
```

## Requirements

- Python 3.11+ with the project dependencies installed via `uv sync`
  (runtime is stdlib-only; the dashboard uses Tailwind, Alpine.js and Plotly
  loaded from CDN).
- Optional: a Gmail account and App Password to enable email sending.

## Run it

```bash
uv run python monitor.py
```

Run it periodically to check for new stock (e.g. cron every 5 minutes, replaced
by the scheduled GitHub Actions workflow if you use the hosted deployment):

```crontab
*/5 * * * * cd /path/to/byd && /path/to/byd/.venv/bin/python3 /path/to/byd/monitor.py >> /path/to/byd/monitor.log 2>&1
```

## Models tracked

All 12 BYD models: Atto 1, Atto 2, Atto 3, Seal, Seal 6, Seal 6 Touring,
Sealion 5, Sealion 6, Sealion 7, Sealion 8, Shark 6, Dolphin.

Paint colours: 25 known colour tokens (Apricity White, Arctic Blue, Arctic
White, Atlantis Grey, Aurora White, Black, Black Brown, Black Grey, Blue Grey,
Cosmos Black, Dark Aquamarine, Deep Sea Blue, Great White, Grey Black, Harbour
Grey, Mist Grey, Outback Orange, Pine Lime, Ridge Grey, Sage Green, Shark Grey,
Ski White, Stone Grey, Thaumas Black, Tidal Black). Unknown colours fall back
to "Unknown".

## Files

- `monitor.py` — the monitoring script.
- `graph.py` — renders `index.html` with the model-spotlight dashboard.
- `index.html` — the generated interactive page (served on GitHub Pages).
- `history.csv` — one row per (state, model, variant, colour) per poll.
- `history-legacy.csv` — pre-multi-model Atto-2-only history (archived).
- `state.json` — stock numbers already seen (so you're not re-notified).
- `notifications.log` — every new Atto 2 Dynamic match, with timestamp,
  stock #, price, status and pickup location.
- `.env.example` — template for the email credentials.

## Dashboard

`index.html` is a model-spotlight page: pick a model from the chip bar to
see its colour breakdown (bar chart), variant time-series (line chart), and
per-state counts. Built with Tailwind CSS, Alpine.js and Plotly.js, all
loaded from CDN — no build step required.

## Enabling email notifications

Email delivery is built in but disabled until credentials are provided. Gmail
removed "Less Secure Apps" access, so you must create an **App Password**:

1. Enable 2-Step Verification on the Gmail account you'll send from:
   <https://myaccount.google.com/security>
2. Create an App Password: <https://myaccount.google.com/apppasswords>
   (choose "Other", name it e.g. `byd-monitor`).
3. Set the three environment variables and run:
   ```bash
   export TO_EMAIL=you@example.com
   export GMAIL_USER=<your-gmail-address>
   export GMAIL_APP_PASSWORD=<16-char-app-password>
   uv run python monitor.py
   ```

When a new Atto 2 Dynamic is found in any state, you'll get an email with the
stock number, price, status and pickup location.

## Filtering

Tunable constants at the top of `monitor.py`:

- `TARGET_STATES` — which state token(s) to watch.
  Default is all states: `{"do-wa", "do-vic", "do-nsw", "do-qld", "do-sa",
  "do-act", "do-nt", "do-tas"}`. Set to `{"do-wa"}` to watch WA only.
- `TARGET_MODEL` — model token (default `do-atto-2`).
- `TARGET_VARIANT` — variant token (default `do-dynamic`).
- `INVENTORY_URL` — the page to fetch.

## Scheduled run

The monitor and graph run automatically via GitHub Actions every 10 minutes.
The generated history, graph and page are committed back to the repo and
served on GitHub Pages at:

    https://kehh.github.io/byd-stock-monitor/

(Set the Pages source to "Deploy from a branch" → `main` → `/` root.)

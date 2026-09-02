# BYD Atto 2 Dynamic Stock Monitor

Monitors the EVDealer Group BYD inventory page for a **BYD Atto 2 Dynamic**
becoming available anywhere in **Australia (all states)**, and sends an email
to `you@example.com` when one appears.

## How it works

The script fetches the server-rendered inventory page
(`https://evdealergroup-byd.com.au/inventory?type=d`), parses every vehicle
card, and prints a table of **Atto 2** units counted by state and variant
(Dynamic, Premium, plus any demo models). Newly-seen **Dynamic** units are
recorded in `notifications.log` and emailed if email is enabled.

## Dependencies

Managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Then run the monitor and graph generator:

```bash
uv run python monitor.py
uv run python graph.py
```

## Requirements

- Python 3 (stdlib only — no third-party packages).
- Optional: a Gmail account and App Password to enable email sending.

## Run it

```bash
python3 monitor.py
```

Run it periodically to check for new stock (e.g. cron every 5 minutes):

```crontab
*/5 * * * * cd /path/to/byd/code/byd && /path/to/byd/code/byd/venv/bin/python3 /path/to/byd/code/byd/monitor.py >> /path/to/byd/code/byd/monitor.log 2>&1
```

## Files

- `monitor.py` — the monitoring script.
- `state.json` — stock numbers already seen (so you're not re-notified).
- `notifications.log` — every new match, with timestamp, stock #, price,
  status and pickup location.
- `.env.example` — template for the email credentials.

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
   python3 monitor.py
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

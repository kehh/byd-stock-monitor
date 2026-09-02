#!/usr/bin/env python3
"""
Monitor the BYD Dealer Group inventory for a BYD Atto 2 in any Australian
state, and record a notification when a new Dynamic unit appears.

Current behaviour:
  - Fetches the inventory page HTML.
  - Parses every vehicle card.
  - Prints a table of Atto 2 units (Dynamic and Premium variants, plus any
    demo models) counted by state.
  - Tracks previously-seen stock numbers in state.json.
  - For any newly-seen Dynamic matching vehicle, appends a line to
    notifications.log (currently the delivery endpoint).

EMAIL SENDING (dormant):
  Email delivery is built in but disabled until credentials are provided via
  environment variables. To enable, set all three of:
      TO_EMAIL             e.g. you@example.com
      GMAIL_USER           a Gmail address used to send (the 'from')
      GMAIL_APP_PASSWORD   a Gmail App Password for GMAIL_USER
  Then the script will email a summary every time a new match is found.
  See README.md for how to create an App Password.

Run manually:  python3 monitor.py
Intended to be run periodically (e.g. cron every 5 minutes).
"""

from __future__ import annotations

import csv
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent

INVENTORY_URL = "https://evdealergroup-byd.com.au/inventory?type=d"
STATE_FILE = BASE_DIR / "state.json"
LOG_FILE = BASE_DIR / "notifications.log"
HISTORY_FILE = BASE_DIR / "history.csv"
HISTORY_HEADER = ("timestamp_utc", "state", "variant", "count", "stock_numbers")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Card HTML looks like:
#   <div class="col vehicle mt-0 756532 do-act do-available-now do-atto-1 do-dynamic do-wa ...">
# State tokens: do-wa, do-vic, do-nsw, do-qld, do-sa, do-act, do-nt, do-tas
TARGET_STATES = {"do-wa", "do-vic", "do-nsw", "do-qld", "do-sa", "do-act", "do-nt", "do-tas"}
TARGET_MODEL = "do-atto-2"
TARGET_VARIANT = "do-dynamic"

TRUE_STATUSES = {"do-available-now", "do-in-transit"}

# Human-readable names for the state tokens used in card classes.
STATE_NAMES = {
    "do-wa": "WA",
    "do-vic": "VIC",
    "do-nsw": "NSW",
    "do-qld": "QLD",
    "do-sa": "SA",
    "do-act": "ACT",
    "do-nt": "NT",
    "do-tas": "TAS",
}

REQUEST_TIMEOUT = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_state() -> set[str]:
    try:
        raw = STATE_FILE.read_text()
        data = json.loads(raw)
        return set(data.get("seen_stock_numbers", []))
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return set()


def save_state(seen: set[str]) -> None:
    STATE_FILE.write_text(json.dumps({"seen_stock_numbers": sorted(seen)}, indent=2) + "\n")


def fetch_inventory_html() -> str:
    req = Request(INVENTORY_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def parse_cards(html: str) -> list[dict]:
    """Extract every vehicle card from the page into a dict."""
    cards = []
    pattern = re.compile(
        r'<div class="col vehicle mt-0 ([^"]*)"(.*?)'
        r'(?=<div class="col vehicle mt-0 |</body>)',
        re.DOTALL,
    )
    for classes, body in pattern.findall(html):
        tokens = set(classes.split())

        title_match = re.search(r'card-title text-nowrap">([^<]*)', body)
        variant_match = re.search(r'card-subtitle text-muted">([^<]*)', body)
        stock_match = re.search(r'(?:In-stock|In-transit) #(\d+)', body)
        price_match = re.search(r'card-title text-nowrap">\$([^<]*)', body)
        proc_match = re.search(r'(\d{4} Model)', body)
        location = parse_location(body, classes)

        status = "available" if "do-available-now" in tokens else (
            "in-transit" if "do-in-transit" in tokens else "unknown"
        )

        cards.append(
            {
                "stock_number": stock_match.group(1) if stock_match else None,
                "title": title_match.group(1).strip() if title_match else None,
                "variant": variant_match.group(1).strip() if variant_match else None,
                "price": price_match.group(1).strip() if price_match else None,
                "location": location,
                "year": proc_match.group(1) if proc_match else None,
                "status": status,
                "state": [t for t in tokens if t.startswith("do-") and t != "do-n"],
            }
        )
    return cards


def parse_location(body: str, classes: str) -> str | None:
    """Derive a human-readable location for a card.

    The site uses two formats for the pickup/registration line:
      - "Pickup from BYD <dealer> with <STATE> registration"
      - "Available for pickup and registration in <STATE>"
    Falls back to the state token present in the card classes.
    """
    pickup = re.search(r'Pickup from ([^<]+?)\s*(?:with|reg|$)', body)
    if pickup:
        loc = pickup.group(1).strip()
        if loc:
            return loc

    reg_state = re.search(r'registration in ([A-Z]{2,3})', body)
    if reg_state:
        return reg_state.group(1)

    state_tokens = set(classes.split())
    for tok in state_tokens:
        if tok in STATE_NAMES:
            return STATE_NAMES[tok]
    return None


def is_atto2(card: dict) -> bool:
    """True for any Atto 2 card (any variant) with a stock number."""
    state_tokens = set(card["state"])
    model = card["title"] or ""
    return (
        (TARGET_MODEL in state_tokens or "atto 2" in model.lower())
        and card["stock_number"] is not None
        and card["status"] in {"available", "in-transit"}
    )


def is_target(card: dict) -> bool:
    state_tokens = set(card["state"])
    model = card["title"] or ""
    variant = card["variant"] or ""
    return (
        bool(TARGET_STATES & state_tokens)
        and (TARGET_MODEL in state_tokens or "atto 2" in model.lower())
        and (TARGET_VARIANT in state_tokens or "dynamic" in variant.lower())
        and card["stock_number"] is not None
        and card["status"] in {"available", "in-transit"}
    )


def send_email(matches: list[dict]) -> None:
    """Email a summary of new matches. Skips silently if credentials missing.

    Enabled once TO_EMAIL, GMAIL_USER and GMAIL_APP_PASSWORD are set.
    """

    to_email = os.environ.get("TO_EMAIL", "").strip()
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

    if not (to_email and gmail_user and app_password):
        print("Email disabled: set TO_EMAIL, GMAIL_USER and GMAIL_APP_PASSWORD to enable.")
        return

    lines = [
        "A BYD Atto 2 Dynamic has become available in Australia!\n",
        f"Found {len(matches)} matching vehicle(s):",
        "",
    ]
    for m in matches:
        lines.append(f"- Stock #{m['stock_number']}")
        lines.append(f"  Title:  {m['title']}")
        lines.append(f"  Price:  ${m['price']}")
        lines.append(f"  Status: {m['status']}")
        lines.append(f"  Where:  {m['location']}")
        lines.append(f"  Link:   https://evdealergroup-byd.com.au/inventory?type=d")
        lines.append("")

    msg = MIMEText("\n".join(lines))
    msg["Subject"] = f"BYD Atto 2 Dynamic now available (x{len(matches)})"
    msg["From"] = gmail_user
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls()
        server.login(gmail_user, app_password)
        server.send_message(msg)

    print(f"Email sent to {to_email}")


def count_by_state(cards: list[dict]) -> dict[str, dict[str, int]]:
    """Return {state_name: {variant_name: count}} for a list of matching cards.

    Variants counted are those advertised in the card variant field (e.g.
    "Dynamic", "Premium") plus "Demo" for any demonstration units.
    """
    counts: dict[str, dict[str, int]] = {}
    for c in cards:
        for tok in c["state"]:
            if tok in STATE_NAMES:
                name = STATE_NAMES[tok]
                variant = "Demo" if is_demo(c) else (c["variant"] or "Unknown")
                per_state = counts.setdefault(name, {})
                per_state[variant] = per_state.get(variant, 0) + 1
                break
    return counts


def is_demo(card: dict) -> bool:
    """True if the card is a demonstration model."""
    text = " ".join(
        [
            card["title"] or "",
            card["variant"] or "",
            " ".join(card["state"]),
        ]
    ).lower()
    return "demo" in text or "demonstration" in text


def variant_of(card: dict) -> str:
    """Return the variant label of a card."""
    return "Demo" if is_demo(card) else (card.get("variant") or "Unknown")


def collect_stock_numbers(cards: list[dict], state: str) -> list[str]:
    """Return sorted stock numbers found for a given state code."""
    numbers = []
    for c in cards:
        state_tokens = set(c["state"])
        if any(tok in STATE_NAMES and STATE_NAMES[tok] == state for tok in state_tokens):
            if c.get("stock_number"):
                numbers.append(c["stock_number"])
    return sorted(numbers)


def append_history(
    cards: list[dict],
    counts: dict[str, dict[str, int]],
    timestamp: str | None = None,
) -> int:
    """Append one row per (state, variant) to HISTORY_FILE. Returns rows written."""
    ts = timestamp or utc_now()
    exists = HISTORY_FILE.exists()
    rows_written = 0
    with HISTORY_FILE.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_HEADER)
        if not exists:
            writer.writeheader()
        for state in sorted(counts):
            per_state = counts[state]
            stocks = collect_stock_numbers(cards, state)
            for variant in ["Dynamic", "Premium", "Demo", "Unknown"]:
                if variant not in per_state:
                    continue
                writer.writerow(
                    {
                        "timestamp_utc": ts,
                        "state": state,
                        "variant": variant,
                        "count": per_state[variant],
                        "stock_numbers": ";".join(stocks),
                    }
                )
                rows_written += 1
    return rows_written


def print_state_table(counts: dict[str, dict[str, int]]) -> None:
    """Print a table of per-state variant counts for Atto 2."""
    if not counts:
        print("No Atto 2 vehicles found.")
        return

    variants = ["Dynamic", "Premium", "Demo"]
    present = sorted({v for per_state in counts.values() for v in per_state})
    order = [v for v in variants if v in present] + [
        v for v in present if v not in variants
    ]

    header = "State   | " + " | ".join(f"{v:<9}" for v in order) + " | Total"
    print("Atto 2 units by state:") 
    print(header)
    print("-" * len(header))

    grand_total = 0
    for state in sorted(counts, key=lambda s: -sum(counts[s].values())):
        row = counts[state]
        total = sum(row.values())
        grand_total += total
        cells = " | ".join(f"{row.get(v, 0):<9}" for v in order)
        print(f"{state:<7} | " + cells + f" | {total}")

    print("-" * len(header))
    total_cells = " | ".join(
        f"{sum(r.get(v, 0) for r in counts.values()):<9}" for v in order
    )
    print(f"{'Total':<7} | " + total_cells + f" | {grand_total}")


def log_matches(matches: list[dict]) -> None:
    ts = utc_now()
    with LOG_FILE.open("a") as f:
        for m in matches:
            f.write(
                f"[{ts}] NEW MATCH - stock#{m['stock_number']} | {m['title']} "
                f"| {m['variant']} | ${m['price']} | {m['status']} | {m['location']}\n"
            )
    print(f"Logged {len(matches)} new match(es) to {LOG_FILE.name}")


def main() -> int:
    print(f"[{utc_now()}] Fetching inventory...")
    try:
        html = fetch_inventory_html()
    except Exception as exc:
        print(f"Error fetching inventory: {exc}", file=sys.stderr)
        return 1

    cards = parse_cards(html)
    print(f"Parsed {len(cards)} vehicle card(s).")

    targets = [c for c in cards if is_target(c)]
    print(f"Matches for Atto 2 Dynamic (all states): {len(targets)}")

    atto2_cards = [c for c in cards if is_atto2(c)]
    by_state = count_by_state(atto2_cards)
    print_state_table(by_state)
    rows = append_history(atto2_cards, by_state)
    print(f"Logged {rows} history row(s) to {HISTORY_FILE.name}")

    seen = load_state()
    new_matches = [t for t in targets if t["stock_number"] not in seen]

    if new_matches:
        seen.update(t["stock_number"] for t in new_matches)
        save_state(seen)
        log_matches(new_matches)
        send_email(new_matches)
    else:
        print("No new matches.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

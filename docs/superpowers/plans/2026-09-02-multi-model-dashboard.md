# Multi-Model Dashboard with Colour Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track all 12 BYD models (and ~25 paint colours) in `history.csv` and render a model-spotlight dashboard (colour breakdown + variant time-series + per-state counts) with Tailwind + Alpine.js.

**Architecture:** `monitor.py` gets two curated catalogs (`MODELS`, `COLOURS`) that map card class tokens to display names; `parse_cards` adds `model`/`colour` fields; `collect_counts`/`append_history` write one row per (state, model, variant, colour) cell. `graph.py` reads the new schema and emits a self-contained `index.html` (Tailwind + Alpine.js + Plotly all via CDN) where an Alpine chip bar selects the spotlight model. Notifications stay byte-for-byte Atto 2 Dynamic.

**Tech Stack:** Python 3 stdlib, csv, Plotly.js CDN, Tailwind CSS CDN, Alpine.js CDN, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-09-02-multi-model-dashboard-design.md`

## Global Constraints

- **History schema:** `timestamp_utc,state,model,variant,colour,count,stock_numbers` — one row per present cell per poll.
- **Notification behaviour unchanged:** `is_target`, `is_atto2`, `send_email`, `log_matches`, `load_state`, `save_state` are untouched. No email-scope change.
- **New `history.csv` starts fresh.** The old Atto-2-only file is archived to `history-legacy.csv` (committed) in Task 5.
- **No new runtime dependencies.** Python side stays stdlib-only (`dependencies = []` in `pyproject.toml`); all UI assets load from CDN.
- **Known tokens must resolve exactly once.** Every `do-*` card token is either model, variant, state, colour, wheel, status, or misc. `do-15steel` / `do-18blackalloy` are **wheels**, never colours.
- **Unknown fallback:** any card with no matching model token → `model="Unknown"`; no matching colour token → `colour="Unknown"`.
- **Deterministic tests.** No test may hit the network; the live token set is hardcoded as `LIVE_TOKENS`.
- Run tests with `uv run pytest`. The repo root is on `pythonpath` via `[tool.pytest.ini_options] pythonpath = ["."]`.

---

### Task 1: Model & colour catalogs, card parsing, token invariant

**Files:**
- Modify: `monitor.py` (constants ~line 47-73, `parse_cards` ~line 101-135)
- Create: `tests/test_tokens.py`

**Interfaces:**
- Produces:
  - `MODELS: dict[str, str]` — token → display name (12 entries)
  - `COLOURS: dict[str, str]` — token → display name (25 entries)
  - `MODEL_TOKENS`, `COLOUR_TOKENS` — `set(MODELS)`, `set(COLOURS)`
  - `VARIANT_TOKENS`, `STATUS_TOKENS`, `MISC_TOKENS` — string sets
  - `WHEEL_RE: re.Pattern` — compile pattern for wheel tokens
  - `model_of(card: dict) -> str` and `colour_of(card: dict) -> str`
  - `parse_cards` cards now include `model` and `colour` keys

- [ ] **Step 1: Write the failing tests** in `tests/test_tokens.py`

```python
import monitor

LIVE_TOKENS = {
    "do-allmodel", "do-n", "do-available-now", "do-in-transit", "do-arriving-soon",
    "do-wa", "do-vic", "do-nsw", "do-qld", "do-sa", "do-act", "do-nt", "do-tas",
    "do-atto-1", "do-atto-2", "do-atto-3", "do-seal", "do-seal-6", "do-seal-6-touring",
    "do-sealion-5", "do-sealion-6", "do-sealion-7", "do-sealion-8", "do-shark-6", "do-dolphin",
    "do-essential", "do-premium", "do-performance", "do-dynamic", "do-dynamicawd",
    "do-dynamicfwd", "do-dynamiccabchassis", "do-dynamicextended", "do-premiumextended",
    "do-premiumawd",
    "do-15steel", "do-16alloy", "do-17alloy", "do-17alloywheels", "do-18alloy",
    "do-18alloywheels", "do-18blackalloy", "do-19alloywheels", "do-20alloy",
    "do-20alloywheels", "do-21alloy",
    "do-apricitywhite", "do-arcticblue", "do-arcticwhite", "do-atlantisgrey",
    "do-aurorawhite", "do-black", "do-blackbrown", "do-blackgrey", "do-bluegrey",
    "do-cosmosblack", "do-darkaquamarine", "do-deepseablue", "do-greatwhite",
    "do-greyblack", "do-harbourgrey", "do-mistgrey", "do-outbackorange", "do-pinelime",
    "do-ridgegrey", "do-sagegreen", "do-sharkgrey", "do-skiwhite", "do-stonegrey",
    "do-thaumasblack", "do-tidalblack",
}


def test_catalogs_are_disjoint():
    assert monitor.MODEL_TOKENS & monitor.COLOUR_TOKENS == set()
    assert monitor.MODEL_TOKENS & monitor.VARIANT_TOKENS == set()
    assert monitor.MODEL_TOKENS & set(monitor.STATE_NAMES) == set()


def test_every_live_token_resolves_to_a_known_category():
    for tok in LIVE_TOKENS:
        resolved = (
            tok in monitor.MODEL_TOKENS
            or tok in monitor.COLOUR_TOKENS
            or tok in monitor.STATE_NAMES
            or tok in monitor.VARIANT_TOKENS
            or tok in monitor.STATUS_TOKENS
            or tok in monitor.MISC_TOKENS
            or monitor.WHEEL_RE.match(tok) is not None
        )
        assert resolved, f"Unresolved token: {tok}"


def test_model_of_maps_token():
    card = {"state": ["do-allmodel", "do-atto-2", "do-vic"]}
    assert monitor.model_of(card) == "Atto 2"


def test_model_of_falls_back_to_unknown():
    card = {"state": ["do-allmodel", "do-vic"]}
    assert monitor.model_of(card) == "Unknown"


def test_colour_of_maps_token():
    card = {"state": ["do-allmodel", "do-thaumasblack", "do-wa"]}
    assert monitor.colour_of(card) == "Thaumas Black"


def test_colour_of_falls_back_to_unknown():
    card = {"state": ["do-allmodel", "do-atto-2", "do-wa"]}
    assert monitor.colour_of(card) == "Unknown"


def test_parse_cards_extracts_model_and_colour():
    html = (
        "<html><body>"
        '<div class="col vehicle mt-0 1001 do-allmodel do-atto-2 do-dynamic '
        'do-thaumasblack do-available-now do-wa">'
        "<h3 class=\"card-title text-nowrap\">BYD ATTO 2</h3>"
        '<h6 class="card-subtitle text-muted">Dynamic</h6>'
        '<span class="d-block text-muted fs-small">In-stock #1001</span>'
        "</div></body></html>"
    )
    cards = monitor.parse_cards(html)
    assert len(cards) == 1
    assert cards[0]["model"] == "Atto 2"
    assert cards[0]["colour"] == "Thaumas Black"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: FAIL — `AttributeError: module 'monitor' has no attribute 'MODEL_TOKENS'` etc.

- [ ] **Step 3: Add the catalogs and maps to `monitor.py`** right after the existing `STATE_NAMES` (line ~73)

```python
# Model tokens present in card classes, token -> display name.
MODELS = {
    "do-atto-1": "Atto 1",
    "do-atto-2": "Atto 2",
    "do-atto-3": "Atto 3",
    "do-seal": "Seal",
    "do-seal-6": "Seal 6",
    "do-seal-6-touring": "Seal 6 Touring",
    "do-sealion-5": "Sealion 5",
    "do-sealion-6": "Sealion 6",
    "do-sealion-7": "Sealion 7",
    "do-sealion-8": "Sealion 8",
    "do-shark-6": "Shark 6",
    "do-dolphin": "Dolphin",
}

# Paint colour tokens present in card classes. Wheel tokens such as
# do-15steel / do-18blackalloy are NOT colours and do not belong here.
COLOURS = {
    "do-apricitywhite": "Apricity White",
    "do-arcticblue": "Arctic Blue",
    "do-arcticwhite": "Arctic White",
    "do-atlantisgrey": "Atlantis Grey",
    "do-aurorawhite": "Aurora White",
    "do-black": "Black",
    "do-blackbrown": "Black Brown",
    "do-blackgrey": "Black Grey",
    "do-bluegrey": "Blue Grey",
    "do-cosmosblack": "Cosmos Black",
    "do-darkaquamarine": "Dark Aquamarine",
    "do-deepseablue": "Deep Sea Blue",
    "do-greatwhite": "Great White",
    "do-greyblack": "Grey Black",
    "do-harbourgrey": "Harbour Grey",
    "do-mistgrey": "Mist Grey",
    "do-outbackorange": "Outback Orange",
    "do-pinelime": "Pine Lime",
    "do-ridgegrey": "Ridge Grey",
    "do-sagegreen": "Sage Green",
    "do-sharkgrey": "Shark Grey",
    "do-skiwhite": "Ski White",
    "do-stonegrey": "Stone Grey",
    "do-thaumasblack": "Thaumas Black",
    "do-tidalblack": "Tidal Black",
}

MODEL_TOKENS = set(MODELS)
COLOUR_TOKENS = set(COLOURS)

VARIANT_TOKENS = {
    "do-essential", "do-premium", "do-performance", "do-dynamic", "do-dynamicawd",
    "do-dynamicfwd", "do-dynamiccabchassis", "do-dynamicextended", "do-premiumextended",
    "do-premiumawd",
}

STATUS_TOKENS = {"do-available-now", "do-in-transit", "do-arriving-soon"}

MISC_TOKENS = {"do-allmodel", "do-n"}

# Wheel tokens: do-15steel, do-16alloy, do-18blackalloy, do-20alloywheels, ...
WHEEL_RE = re.compile(r"do-\d+(?:black)?(?:alloywheels?|steel)$")
```

- [ ] **Step 4: Add `model_of` / `colour_of` functions** above `parse_cards` (after `parse_location`)

```python
def model_of(card: dict) -> str:
    """Return the canonical model display name for a card, or \"Unknown\"."""
    for tok in card["state"]:
        if tok in MODELS:
            return MODELS[tok]
    return "Unknown"


def colour_of(card: dict) -> str:
    """Return the canonical paint display name for a card, or \"Unknown\"."""
    for tok in card["state"]:
        if tok in COLOURS:
            return COLOURS[tok]
    return "Unknown"
```

- [ ] **Step 5: Add `model` and `colour` keys in `parse_cards`** — in the `cards.append({...})` block (line ~123), add them after the existing keys:

```python
            {
                "stock_number": stock_match.group(1) if stock_match else None,
                "title": title_match.group(1).strip() if title_match else None,
                "variant": variant_match.group(1).strip() if variant_match else None,
                "price": price_match.group(1).strip() if price_match else None,
                "location": location,
                "year": proc_match.group(1) if proc_match else None,
                "status": status,
                "state": [t for t in tokens if t.startswith("do-") and t != "do-n"],
                "model": "",  # filled in below via the token maps
                "colour": "",
            }
```

Then after the `cards.append(...)` call, fill the empty strings from the token lists:

```python
        cards[-1]["model"] = model_of(cards[-1])
        cards[-1]["colour"] = colour_of(cards[-1])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_tokens.py -v`
Expected: 8 PASS

- [ ] **Step 7: Commit**

```bash
git add monitor.py tests/test_tokens.py
git commit -m "feat: model and colour catalogs with card parsing"
```

---

### Task 2: `collect_counts` + new-schema history writing

**Files:**
- Modify: `monitor.py` (constants `HISTORY_HEADER` line 47, `count_by_state` line 228, `append_history` line 274, `print_state_table` line 306, `main` line 349)
- Modify: `tests/test_history.py`

**Interfaces:**
- Consumes: `MODELS`, `COLOURS`, `model_of`, `colour_of`, `variant_of`, `is_demo` from Task 1.
- Produces:
  - `HISTORY_HEADER` becomes `("timestamp_utc", "state", "model", "variant", "colour", "count", "stock_numbers")`
  - `collect_counts(cards: list[dict]) -> dict[tuple[str, str, str, str], list[str]]` — validated cards → `{(state, model, variant, colour): [stock_numbers]}`
  - `append_history(cards: list[dict], timestamp: str | None = None) -> int` — **signature changed** (no more `counts` arg), returns rows written
  - `print_summary(cells: dict[tuple[str, str, str, str], list[str]]) -> None`
  - `main()` drops `count_by_state`/`print_state_table` usage; writes all-model history; notifications unchanged.

- [ ] **Step 1: Write the failing tests** — replace `tests/test_history.py` with:

```python
import csv

import monitor


def sample_cards():
    return [
        {
            "stock_number": "1001", "title": "BYD ATTO 2", "variant": "Dynamic",
            "price": None, "location": None, "year": None, "status": "available",
            "model": "Atto 2", "colour": "Thaumas Black",
            "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic",
                      "do-thaumasblack", "do-available-now"],
        },
        {
            "stock_number": "1002", "title": "BYD ATTO 2", "variant": "Dynamic",
            "price": None, "location": None, "year": None, "status": "in-transit",
            "model": "Atto 2", "colour": "Aurora White",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-dynamic",
                      "do-aurorawhite", "do-in-transit"],
        },
        {
            "stock_number": "1003", "title": "BYD ATTO 2", "variant": "Premium",
            "price": None, "location": None, "year": None, "status": "available",
            "model": "Atto 2", "colour": "Thaumas Black",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-premium",
                      "do-thaumasblack", "do-available-now"],
        },
    ]


def test_variant_of_labels():
    dyn = sample_cards()[0]
    assert monitor.variant_of(dyn) == "Dynamic"
    prem = sample_cards()[2]
    assert monitor.variant_of(prem) == "Premium"


def test_collect_counts_keys_cells_by_state_model_variant_colour():
    cells = monitor.collect_counts(sample_cards())
    assert ("VIC", "Atto 2", "Dynamic", "Thaumas Black") in cells
    assert cells[("VIC", "Atto 2", "Dynamic", "Thaumas Black")] == ["1001"]
    assert cells[("WA", "Atto 2", "Dynamic", "Aurora White")] == ["1002"]
    assert cells[("WA", "Atto 2", "Premium", "Thaumas Black")] == ["1003"]


def test_collect_counts_skips_invalid_cards():
    bad = {
        "stock_number": None, "title": "BYD ATTO 2", "variant": "Dynamic",
        "price": None, "location": None, "year": None, "status": "available",
        "model": "Atto 2", "colour": "Black",
        "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic"],
    }
    assert monitor.collect_counts([bad]) == {}


def test_append_history_writes_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    rows = monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    assert rows == 3

    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert data[0]["state"] == "VIC"
    assert data[0]["model"] == "Atto 2"
    assert data[0]["variant"] == "Dynamic"
    assert data[0]["colour"] == "Thaumas Black"
    assert data[0]["count"] == "1"
    assert data[0]["stock_numbers"] == "1001"
    assert data[0]["timestamp_utc"] == "2026-01-01 00:00:00 UTC"
    # WA has two distinct cells -> two rows
    wa_rows = [r for r in data if r["state"] == "WA"]
    assert len(wa_rows) == 2


def test_append_history_appends_not_overwrites(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:05:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 6
    assert data[3]["timestamp_utc"] == "2026-01-01 00:05:00 UTC"


def test_header_includes_model_and_colour(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        reader = csv.DictReader(f)
        assert "model" in reader.fieldnames
        assert "colour" in reader.fieldnames
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_history.py -v`
Expected: FAIL — `TypeError: collect_counts() ... ` (not yet defined) and header/row mismatches.

- [ ] **Step 3: Change `HISTORY_HEADER`** (line 47)

```python
HISTORY_HEADER = ("timestamp_utc", "state", "model", "variant", "colour", "count", "stock_numbers")
```

- [ ] **Step 4: Replace `count_by_state` (line 228) with `collect_counts`**

```python
def collect_counts(cards: list[dict]) -> dict[tuple[str, str, str, str], list[str]]:
    """Return {(state, model, variant, colour): [stock_numbers]} for validated cards.

    A card is validated when it has a stock number and a status of
    \"available\" or \"in-transit\" (same rule the Atto 2 filter used).
    """
    cells: dict[tuple[str, str, str, str], list[str]] = {}
    for c in cards:
        if c.get("stock_number") is None or c.get("status") not in {"available", "in-transit"}:
            continue
        state = next((STATE_NAMES[t] for t in c["state"] if t in STATE_NAMES), None)
        if state is None:
            continue
        key = (state, c.get("model") or "Unknown", variant_of(c), c.get("colour") or "Unknown")
        cells.setdefault(key, []).append(c["stock_number"])
    return cells
```

- [ ] **Step 5: Rewrite `append_history` (line 274)** — new signature, writes one row per cell

```python
def append_history(
    cards: list[dict],
    timestamp: str | None = None,
) -> int:
    """Append one row per (state, model, variant, colour) cell. Returns rows written."""
    ts = timestamp or utc_now()
    cells = collect_counts(cards)
    exists = HISTORY_FILE.exists()
    rows_written = 0
    with HISTORY_FILE.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_HEADER)
        if not exists:
            writer.writeheader()
        for (state, model, variant, colour), stocks in sorted(cells.items()):
            writer.writerow(
                {
                    "timestamp_utc": ts,
                    "state": state,
                    "model": model,
                    "variant": variant,
                    "colour": colour,
                    "count": len(stocks),
                    "stock_numbers": ";".join(sorted(stocks)),
                }
            )
            rows_written += 1
    return rows_written
```

- [ ] **Step 6: Replace `print_state_table` (line 306) with `print_summary`**

```python
def print_summary(cells: dict[tuple[str, str, str, str], list[str]]) -> None:
    """Print total units per model (and state totals for the top model)."""
    if not cells:
        print("No vehicles found.")
        return
    by_model: dict[str, int] = {}
    for (state, model, variant, colour), stocks in sorted(cells.items()):
        by_model[model] = by_model.get(model, 0) + len(stocks)

    print("Units by model:")
    for model, n in sorted(by_model.items(), key=lambda kv: -kv[1]):
        print(f"  {model:<14} {n}")
    print(f"  {'Total':<14} {sum(by_model.values())}")
```

- [ ] **Step 7: Update `main()` (line 349)** — write all-model history, keep notifications

Replace lines 357-367 section so that it reads:

```python
    cards = parse_cards(html)
    print(f"Parsed {len(cards)} vehicle card(s).")

    targets = [c for c in cards if is_target(c)]
    print(f"Matches for Atto 2 Dynamic (all states): {len(targets)}")

    cards = [c for c in cards if c.get("model") is not None]
    cells = collect_counts(cards)
    print_summary(cells)
    rows = append_history(cards)
    print(f"Logged {rows} history row(s) to {HISTORY_FILE.name}")
```

(Note: `collect_stock_numbers` and the old `count_by_state`/`print_state_table` are now unused; leave `collect_stock_numbers` in place if still referenced, otherwise remove it — but **do not** alter the notification block after this section.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_history.py -v`
Expected: 6 PASS

- [ ] **Step 9: Commit**

```bash
git add monitor.py tests/test_history.py
git commit -m "feat: track all models by state, variant, and colour in history"
```

---

### Task 3: Graph data builders for the new schema

**Files:**
- Modify: `graph.py` (reuse `load_history`/`to_iso`/`series_to_traces`/`COLORS`)
- Modify: `tests/test_graph.py`

**Interfaces:**
- Consumes: `history.csv` rows with the Task 2 header.
- Produces:
  - `load_history(path: Path) -> list[dict]` — returns `[]` when the header lacks `model` (old schema) or file missing (caller handles missing).
  - `latest_timestamp(rows: list[dict]) -> str`
  - `colour_snapshot(rows: list[dict], model: str, ts: str) -> dict[str, int]`
  - `variant_series(rows: list[dict], model: str) -> dict[str, tuple[list[str], list[int]]]`
  - `per_state_counts(rows: list[dict], model: str, ts: str) -> dict[str, int]`
  - `render_html(rows: list[dict], out_path: Path) -> Path` — **signature changed** from `render_html(series, out_path)`

- [ ] **Step 1: Write the failing tests** — replace `tests/test_graph.py` with:

```python
import csv
import json

import graph


def write_history(tmp_path, rows):
    p = tmp_path / "history.csv"
    fieldnames = ["timestamp_utc", "state", "model", "variant", "colour", "count", "stock_numbers"]
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


EXAMPLE_ROWS = [
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "2", "stock_numbers": "1;2"},
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "WA", "model": "Atto 2",
     "variant": "Premium", "colour": "Aurora White", "count": "1", "stock_numbers": "3"},
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "model": "Sealion 8",
     "variant": "Premium", "colour": "Cosmos Black", "count": "4", "stock_numbers": "4;5;6;7"},
    {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "VIC", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "3", "stock_numbers": "1;2;8"},
    {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "WA", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "2", "stock_numbers": "9;10"},
]


def test_load_history_new_schema(tmp_path):
    p = write_history(tmp_path, EXAMPLE_ROWS)
    rows = graph.load_history(p)
    assert len(rows) == 5
    assert "model" in rows[0]


def test_load_history_rejects_old_schema(tmp_path):
    p = tmp_path / "history.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp_utc", "state", "variant", "count", "stock_numbers"])
        writer.writeheader()
        writer.writerow({"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC",
                         "variant": "Dynamic", "count": "1", "stock_numbers": "1"})
    assert graph.load_history(p) == []


def test_latest_timestamp_returns_max(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    assert graph.latest_timestamp(rows) == "2026-01-01 00:10:00 UTC"


def test_colour_snapshot_filters_to_latest_ts_and_model(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    snap = graph.colour_snapshot(rows, "Atto 2", "2026-01-01 00:10:00 UTC")
    assert snap == {"Thaumas Black": 5}


def test_variant_series_sums_cells_per_poll(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    series = graph.variant_series(rows, "Atto 2")
    assert series["Dynamic"][0] == ["2026-01-01 00:00:00 UTC", "2026-01-01 00:10:00 UTC"]
    assert series["Dynamic"][1] == [2, 5]


def test_per_state_counts_latest_only(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    counts = graph.per_state_counts(rows, "Atto 2", "2026-01-01 00:10:00 UTC")
    assert counts == {"VIC": 3, "WA": 2}


def test_series_to_traces_uses_dates_on_x_axis():
    series = {
        "VIC Dynamic": (["2026-01-01 00:00:00 UTC", "2026-01-02 05:30:00 UTC"], [2, 3]),
    }
    traces = graph.series_to_traces(series)
    assert traces[0]["name"] == "VIC Dynamic"
    assert traces[0]["x"] == ["2026-01-01T00:00:00Z", "2026-01-02T05:30:00Z"]
    assert traces[0]["y"] == [2, 3]


def test_render_html_embeds_dashboard_data(tmp_path):
    p = write_history(tmp_path, EXAMPLE_ROWS)
    rows = graph.load_history(p)
    out = tmp_path / "index.html"
    graph.render_html(rows, out)
    text = out.read_text()
    assert "tailwindcss" in text.lower()
    assert "alpine" in text.lower()
    assert "plotly" in text.lower()
    assert "const MODELS = " in text
    data = json.loads(text.split("const MODELS = ")[1].split(";")[0])
    assert set(data["models"]) == {"Atto 2", "Sealion 8"}
    assert data["snapshots"]["Atto 2"] == {"Thaumas Black": 5}
    assert data["timeseries"]["Atto 2"]["Dynamic"] == {
        "dates": ["2026-01-01T00:00:00Z", "2026-01-01T00:10:00Z"],
        "counts": [2, 5],
    }
    assert data["per_state"]["Atto 2"] == {"VIC": 3, "WA": 2}
    assert "graph.png" not in text


def test_render_html_empty_state(tmp_path):
    out = tmp_path / "index.html"
    graph.render_html([], out)
    assert out.exists()
    assert "No data" in out.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL — `TypeError` on `variant_series`/`colour_snapshot` (undefined) and `render_html` signature mismatch.

- [ ] **Step 3: Update `load_history` and add the build helpers** in `graph.py`

```python
def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and "model" not in rows[0]:
        return []  # old schema
    return rows


def latest_timestamp(rows: list[dict]) -> str:
    return max(r["timestamp_utc"] for r in rows)


def colour_snapshot(rows: list[dict], model: str, ts: str) -> dict[str, int]:
    snap: dict[str, int] = {}
    for r in rows:
        if r["timestamp_utc"] == ts and r["model"] == model:
            snap[r["colour"]] = snap.get(r["colour"], 0) + int(r["count"])
    return snap


def variant_series(rows: list[dict], model: str) -> dict[str, tuple[list[str], list[int]]]:
    points: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["model"] != model:
            continue
        bucket = points.setdefault(r["variant"], {})
        bucket[r["timestamp_utc"]] = bucket.get(r["timestamp_utc"], 0) + int(r["count"])
    series: dict[str, tuple[list[str], list[int]]] = {}
    for variant, ts_counts in points.items():
        ordered = sorted(ts_counts.items())
        series[variant] = ([ts for ts, _ in ordered], [c for _, c in ordered])
    return series


def per_state_counts(rows: list[dict], model: str, ts: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        if r["timestamp_utc"] == ts and r["model"] == model:
            counts[r["state"]] = counts.get(r["state"], 0) + int(r["count"])
    return counts
```

- [ ] **Step 4: Run the graph tests, expected to still fail on `render_html`**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL — the two `render_html` tests (`test_render_html_embeds_dashboard_data`, `test_render_html_empty_state`). That is fine; `render_html` is replaced in Task 4.

- [ ] **Step 5: Commit the builders**

```bash
git add graph.py tests/test_graph.py
git commit -m "feat: graph data builders for multi-model schema"
```

---

### Task 4: Dashboard renderer (Tailwind + Alpine + Plotly)

**Files:**
- Modify: `graph.py` (replace `render_html`, add `_build_dashboard_data`, `colour_traces`, update `main`)
- Modify: `tests/test_graph.py` (render tests currently failing — this task makes them green)

**Interfaces:**
- Consumes: `load_history`, `latest_timestamp`, `colour_snapshot`, `variant_series`, `per_state_counts`, `to_iso`, `series_to_traces`, `COLORS` from Task 3.
- Produces:
  - `_build_dashboard_data(rows) -> dict` with keys `models`, `latest_ts`, `snapshots`, `timeseries`, `per_state`.
  - `colour_traces(snapshot: dict[str, int]) -> list[dict]` — Plotly bar traces, descending by count.
  - `render_html(rows: list[dict], out_path: Path) -> Path` — renders empty state when `rows == []`.
  - `main()` unchanged except empty-history message.

- [ ] **Step 1: Implement `_build_dashboard_data`, `colour_traces`, and the new `render_html`** in `graph.py`, replacing the old `render_html` body

```python
def colour_traces(snapshot: dict[str, int]) -> list[dict]:
    items = sorted(snapshot.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "x": [name for name, _ in items],
            "y": [count for _, count in items],
            "type": "bar",
            "marker": {"color": COLORS[:len(items)] or COLORS},
        }
    ]


def _build_dashboard_data(rows: list[dict]) -> dict:
    ts = latest_timestamp(rows)
    models = sorted({r["model"] for r in rows})
    snapshots = {m: colour_snapshot(rows, m, ts) for m in models}
    timeseries = {}
    for m in models:
        ts_series = {}
        for variant, (dates, counts) in variant_series(rows, m).items():
            ts_series[variant] = {
                "dates": [to_iso(d) for d in dates],
                "counts": counts,
            }
        timeseries[m] = ts_series
    per_state = {m: per_state_counts(rows, m, ts) for m in models}
    return {
        "models": models,
        "latest_ts": ts,
        "snapshots": snapshots,
        "timeseries": timeseries,
        "per_state": per_state,
    }


TAILWIND_CDN = "https://cdn.tailwindcss.com"
ALPINE_CDN = "https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"


def render_html(rows: list[dict], out_path: Path) -> Path:
    if not rows:
        out_path.write_text(
            "<!DOCTYPE html>\n<html><body><h1>BYD Stock Monitor</h1>"
            "<p>No data yet.</p></body></html>\n"
        )
        return out_path

    data = _build_dashboard_data(rows)
    data_json = json.dumps(data)
    first_model = data["models"][0]

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BYD Stock Monitor</title>
<script src="{TAILWIND_CDN}"></script>
<script src="{PLOTLY_CDN}"></script>
<script src="{ALPINE_CDN}" defer></script>
</head>
<body class="bg-slate-100 text-slate-800" x-data="dashboard()" x-init="select('{first_model}')">
<header class="bg-white border-b border-slate-200">
  <div class="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold">BYD Stock Monitor</h1>
      <p class="text-sm text-slate-500">Australian dealership inventory by model, variant &amp; colour. Times are UTC.</p>
    </div>
    <div class="text-right text-sm text-slate-500" x-text="'Latest poll: ' + model.latest_ts"></div>
  </div>
  <nav class="max-w-5xl mx-auto px-6 pb-3 flex flex-wrap gap-2">
    <template x-for="m in model.models" :key="m">
      <button
        type="button"
        class="px-4 py-1.5 rounded-full text-sm font-medium transition"
        :class="selected === m ? 'bg-sky-600 text-white shadow' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'"
        x-text="m"
        @click="select(m)"></button>
    </template>
  </nav>
</header>

<main class="max-w-5xl mx-auto px-6 py-6 space-y-6">
  <section class="bg-white rounded-xl shadow-sm p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold" x-text="selected + ' — colour availability'"></h2>
      <div class="flex items-center gap-3 text-sm">
        <span class="text-slate-500">Total units</span>
        <span class="text-2xl font-bold text-sky-600" x-text="total"></span>
      </div>
    </div>
    <div id="colourChart" class="h-64"></div>
  </section>

  <section class="bg-white rounded-xl shadow-sm p-6">
    <h2 class="text-lg font-semibold mb-1" x-text="selected + ' — units over time'"></h2>
    <p class="text-sm text-slate-500 mb-4">Click a legend entry to show or hide that variant.</p>
    <div id="seriesChart" class="h-80"></div>
  </section>

  <section class="bg-white rounded-xl shadow-sm p-6">
    <h2 class="text-lg font-semibold mb-4" x-text="selected + ' — counts by state'"></h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <template x-for="(count, state) in stateCounts" :key="state">
        <div class="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div class="text-sm text-slate-500" x-text="state"></div>
          <div class="text-2xl font-semibold" x-text="count"></div>
        </div>
      </template>
      <div x-show="Object.keys(stateCounts).length === 0" class="col-span-full text-slate-400 text-sm">No state counts yet.</div>
    </div>
  </section>
</main>

<script>
const MODELS = {data_json};

function dashboard() {{
  return {{
    selected: null,
    model: MODELS,
    get total() {{ return Object.values(this.model.snapshots[this.selected] || {{}}).reduce((a, b) => a + b, 0); }},
    get stateCounts() {{ return this.model.per_state[this.selected] || {{}}; }},
    select(name) {{
      this.selected = name;
      const snap = this.model.snapshots[name] || {{}};
      Plotly.react("colourChart", {{
        x: Object.keys(snap).sort((a, b) => snap[b] - snap[a]),
        y: Object.values(snap).sort((a, b) => b - a),
        type: "bar",
        marker: {{ color: "#0ea5e9" }},
      }}, {{
        xaxis: {{ title: "Colour", tickangle: -30 }},
        yaxis: {{ title: "Units available" }},
        margin: {{ t: 10, r: 10, b: 80, l: 50 }},
        colorway: ["#0ea5e9", "#0369a1", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#f97316", "#14b8a6", "#e11d48", "#84cc16"],
      }});
      const ts = this.model.timeseries[name] || {{}};
      const traces = Object.entries(ts).map(([variant, {dates, counts}], i) => ({{
        name: variant,
        x: dates,
        y: counts,
        mode: "lines+markers",
        line: {{ width: 2 }},
        marker: {{ size: 6 }},
        color: ["#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#14b8a6"][i % 6],
      }}));
      Plotly.react("seriesChart", traces, {{
        xaxis: {{ title: "Date (UTC)" }},
        yaxis: {{ title: "Units available" }},
        legend: {{ orientation: "h", y: -0.25 }},
        margin: {{ t: 10, r: 10, b: 50, l: 50 }},
      }});
    }},
  }};
}}
</script>
</body>
</html>
"""
    out_path.write_text(content)
    return out_path
```

- [ ] **Step 2: Run the full graph test file**

Run: `uv run pytest tests/test_graph.py -v`
Expected: ALL PASS (including the two render tests that failed in Task 4 Step 4).

- [ ] **Step 3: Update `main()`** to call the new signature and handle empty history

```python
def main() -> int:
    rows = load_history(HISTORY_FILE)
    if not rows:
        print("No valid history yet; rendering empty state.", flush=True)
        render_html([], INDEX_FILE)
        return 0
    data = _build_dashboard_data(rows)
    render_html(rows, INDEX_FILE)
    n_models = len(data["models"])
    print(f"Rendered dashboard ({n_models} models) to {INDEX_FILE.name}", flush=True)
    return 0
```

(`INDEX_FILE` and `HISTORY_FILE` already exist at `graph.py:12-13`; no re-adding needed.)

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: ALL PASS (8 graph + 6 history + 8 tokens + 4 monitor = 26 tests)

- [ ] **Step 5: Commit**

```bash
git add graph.py tests/test_graph.py
git commit -m "feat: model-spotlight dashboard with colour breakdown, variants, and state counts"
```

---

### Task 5: Archive legacy history, regenerate, README, final verification

**Files:**
- Modify: `README.md`
- Rename: `history.csv` → `history-legacy.csv`
- Regenerate: fresh `history.csv`, `index.html` via live run

**Interfaces:**
- Consumes: all tasks above.

- [ ] **Step 1: Archive the legacy history and regenerate live data**

```bash
git mv history.csv history-legacy.csv
uv run python -c "
import monitor
html = monitor.fetch_inventory_html()
cards = monitor.parse_cards(html)
cells = monitor.collect_counts(cards)
monitor.print_summary(cells)
rows = monitor.append_history(cards)
print(f'wrote {rows} rows')
"
uv run python graph.py
```

Expected: `history.csv` created with new header and live rows; `index.html` regenerated; console prints per-model totals.

- [ ] **Step 2: Update `README.md`** — replace the "Files" & "Requirements" sections so they describe:
  - Three files you need: `monitor.py`, `graph.py`, and `uv`.
  - It now tracks **all 12 models** (Atto 1/2/3, Seal, Seal 6/Touring, Sealion 5/6/7/8, Shark 6, Dolphin) **and their paint colours** (25 known), one row per (state, model, variant, colour) per poll.
  - Notification emails are still **Atto 2 Dynamic only** (env vars unchanged).
  - `history-legacy.csv` contains the pre-multi-model Atto-2-only history.
  - The dashboard (`index.html`) is a model-spotlight page: pick a model from the chip bar to see its colour breakdown, variant time-series, and per-state counts. It loads Tailwind, Alpine.js, and Plotly from CDN.

- [ ] **Step 3: Verify the generated dashboard by inlining a message header for bot commits is unchanged** — check the workflow still commits exactly:

```bash
cat .github/workflows/monitor.yml | grep -A3 "git add"
```

Expected: `history.csv state.json notifications.log index.html` (history-legacy.csv is committed once here, by this Task's commit; the bot will NOT touch it because the workflow's `git add` list does not include it).

- [ ] **Step 4: Run the full suite and graph regeneration check**

Run:
```bash
uv run pytest -v
uv run python graph.py
test -s index.html && echo "index.html regenerated"
```

Expected: all tests pass, `index.html` non-empty.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: archive legacy history, regenerate dashboard with live multi-model data"
```

- [ ] **Step 6: Final verification**

Run:
```bash
uv run pytest -v
git status --short
git log --oneline -6
```

Expected: suite green; worktree clean apart from any uncommitted runtime files named in `.gitignore`; last commits are the five from Tasks 1-5.

---

## Self-Review

**Spec coverage:**
- Models catalog + parse fields → Task 1 ✓
- Colour catalog + Unknown fallback → Task 1 (`colour_of`, `model_of` fallbacks tested) ✓
- Known-token invariant (live token set) → Task 1 `test_every_live_token_resolves_to_a_known_category` ✓
- `collect_counts`/`append_history` per-cell rows → Task 2 ✓
- Notifications unchanged → Task 2 Step 7 preserves the notification block; no email-scope edits anywhere ✓
- Console per-model summary → Task 2 `print_summary` ✓
- Legacy history archived → Task 5 `git mv history.csv history-legacy.csv` ✓
- Graph builders (loader guard, snapshot, variant series, per-state) → Task 3 ✓
- Dashboard: chip bar, colour bar, variant time-series, per-state block, Tailwind+Alpine+Plotly CDN → Task 4 ✓
- Empty state → Task 3 test + Task 4 `render_html` `rows == []` branch ✓
- Loader tolerance of old schema → Task 3 `test_load_history_rejects_old_schema` ✓
- No workflow change → Task 5 Step 3 ✓
- README → Task 5 Step 2 ✓

**Placeholder scan:** No TBDs, no "add validation" hints; every code step carries full code. The only open reference in Task 4 Step 3's `main()` note is conditional (re-add `INDEX_FILE`/`HISTORY_FILE` if absent) — but they already exist at `graph.py:12-13`, so the note is a guard confirming existing constants.

**Type consistency:**
- `render_html(rows, out_path)` is consistently used across Task 3 tests and Task 4 (old `render_html(series, out_path)` signature is gone everywhere).
- `collect_counts`/`append_history`/`print_summary` signatures match across Task 2 steps and Task 5 Step 1.
- `variant_series` returns `(list[str], list[int])` in Task 3 and Task 4's `_build_dashboard_data` consumes it as `(dates, counts)` — consistent.
- `colour_snapshot` returns `dict[str, int]` consumed by `_build_dashboard_data.snapshots` and asserted in the render test — consistent.
# BYD Stock History Logging & GitHub Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the BYD monitor log Atto 2 stock numbers and per-state/variant counts over time, generate a graph from that history, and schedule it for free on GitHub Actions with GitHub Pages serving the graph.

**Architecture:** `monitor.py` gains a history-append step that writes one row per (state, variant, timestamp) group to `history.csv`. A new `graph.py` reads that CSV and renders `graph.png` + `index.html`. Dependencies are managed by `uv` (only `matplotlib` is non-stdlib). A GitHub Actions workflow runs `monitor.py` + `graph.py` on a cron and commits the generated data/artifacts back, with GitHub Pages serving the repo root.

**Tech Stack:** Python 3.13, stdlib (`urllib`, `csv`, `json`, `re`, `smtplib`, `datetime`), matplotlib, uv, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-09-02-byd-stock-history-deploy-design.md`

## Global Constraints

- Runtime dependency list is exactly: `matplotlib`. No other third-party packages.
- All fetch/parse/email/JSON/CSV logic stays in the Python stdlib.
- History rows: columns exactly `timestamp_utc,state,variant,count,stock_numbers`.
  `timestamp_utc` format `YYYY-MM-DD HH:MM:SS` UTC; `stock_numbers` is a
  semicolon-separated string (empty when count is 0).
- State abbreviations used: `WA VIC NSW QLD SA ACT NT TAS`. Variants: `Dynamic`, `Premium`, `Demo` (only if present).
- `graph.png` and `index.html` are overwritten each run (idempotent).
- On fetch failure, monitor exits non-zero and writes NO partial history row.
- Repo branch is `develop` today; deployment target branch is `main`.
- Git commits use the existing local identity.

---

### Task 1: Set up uv project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Modify: `README.md` (add uv run instructions)

**Interfaces:**
- Consumes: nothing
- Produces: `pyproject.toml` that `uv sync` resolves; `README.md` documenting `uv sync` + `uv run python monitor.py` + `uv run python graph.py`

- [ ] **Step 1: Verify uv is available**

Run: `uv --version`
Expected: version printed.

If uv is not installed, install it via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
then re-run `uv --version`.

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "byd-stock-monitor"
version = "0.1.0"
description = "Monitor BYD Dealer Group inventory for BYD Atto 2 stock and track it over time."
requires-python = ">=3.11"
dependencies = [
    "matplotlib>=3.9",
]

[tool.uv]
package = false
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
.venv/
*.egg-info/
```

- [ ] **Step 4: Install deps and lock**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, matplotlib installed.

- [ ] **Step 5: Append uv usage to `README.md`**

Add a section near the top of `README.md` under `## Requirements` / `## Run it`:

```markdown
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
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore README.md
git commit -m "chore: add uv project scaffolding with matplotlib"
```

---

### Task 2: Add history logging to monitor.py

**Files:**
- Modify: `monitor.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: existing `parse_cards(html) -> list[dict]`, `count_by_state(cards) -> dict[str, dict[str, int]]`, existing card `state` list, existing `utc_now()`.
- Produces:
  - `HISTORY_FILE = BASE_DIR / "history.csv"`
  - `HISTORY_HEADER = ("timestamp_utc", "state", "variant", "count", "stock_numbers")`
  - `append_history(cards: list[dict], counts: dict[str, dict[str, int]], timestamp: str | None = None) -> int` — appends one row per (state, variant) with the stock-number set, returns rows written.
  - `collect_stock_numbers(cards: list[dict], state: str) -> list[str]`
  - `variant_of(card: dict) -> str` — returns the variant label ("Dynamic"/"Premium"/"Demo"/"Unknown").

- [ ] **Step 1: Write the failing test**

Create `tests/test_history.py`:

```python
import csv
import tempfile
from pathlib import Path

import monitor


def sample_cards():
    return [
        {
            "stock_number": "1001", "title": "BYD ATTO 2",
            "variant": "Dynamic", "price": None, "location": None,
            "year": None, "status": "available",
            "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic", "do-available-now"],
        },
        {
            "stock_number": "1002", "title": "BYD ATTO 2",
            "variant": "Dynamic", "price": None, "location": None,
            "year": None, "status": "in-transit",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-dynamic", "do-in-transit"],
        },
        {
            "stock_number": "1003", "title": "BYD ATTO 2",
            "variant": "Premium", "price": None, "location": None,
            "year": None, "status": "available",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-premium", "do-available-now"],
        },
    ]


def test_variant_of_labels():
    dyn = sample_cards()[0]
    assert monitor.variant_of(dyn) == "Dynamic"
    prem = sample_cards()[2]
    assert monitor.variant_of(prem) == "Premium"


def test_append_history_writes_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    counts = monitor.count_by_state(sample_cards())
    rows = monitor.append_history(sample_cards(), counts)
    assert rows == 3  # VIC/Dynamic, WA/Dynamic, WA/Premium

    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert data[0]["state"] == "VIC"
    assert data[0]["variant"] == "Dynamic"
    assert data[0]["count"] == "1"
    assert data[0]["stock_numbers"] == "1001"
    assert data[0]["timestamp_utc"].endswith("UTC")
    # WA has two variants -> two rows
    wa_rows = [r for r in data if r["state"] == "WA"]
    assert len(wa_rows) == 2


def test_append_history_appends_not_overwrites(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    counts = monitor.count_by_state(sample_cards())
    monitor.append_history(sample_cards(), counts, timestamp="2026-01-01 00:00:00 UTC")
    monitor.append_history(sample_cards(), counts, timestamp="2026-01-01 00:05:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 6
    assert data[3]["timestamp_utc"] == "2026-01-01 00:05:00 UTC"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_history.py -v`
Expected: FAIL — `monitor.variant_of` and `monitor.append_history` don't exist yet. (Install pytest as a dev dependency first: `uv add --dev pytest`, then `uv sync`.)

- [ ] **Step 3: Add history constants and functions to monitor.py**

Add near the top (after `LOG_FILE`):

```python
HISTORY_FILE = BASE_DIR / "history.csv"
HISTORY_HEADER = ("timestamp_utc", "state", "variant", "count", "stock_numbers")
```

Add functions (place after `is_demo`):

```python
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
```

- [ ] **Step 4: Add the `import csv` to monitor.py**

Add `import csv` to the stdlib imports block.

- [ ] **Step 5: Call `append_history` from `main()`**

In `main()`, after the `print_state_table(...)` call and before `seen = load_state()`:

```python
    atto2_cards = [c for c in cards if is_atto2(c)]
    by_state = count_by_state(atto2_cards)
    print_state_table(by_state)
    rows = append_history(atto2_cards, by_state)
    print(f"Logged {rows} history row(s) to {HISTORY_FILE.name}")
```

Adjust the existing `by_state = count_by_state([c for c in cards if is_atto2(c)])`
line accordingly (replace it with the two-line version above).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_history.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Run monitor against live site**

Run: `uv run python monitor.py`
Expected: prints `Logged N history row(s) to history.csv`; `history.csv` created with header + rows.

- [ ] **Step 8: Commit**

```bash
git add monitor.py tests/test_history.py history.csv
git commit -m "feat: log Atto 2 stock counts and numbers to history.csv over time"
```

---

### Task 3: Generate graph.png + index.html

**Files:**
- Create: `graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `history.csv` with header `timestamp_utc,state,variant,count,stock_numbers`.
- Produces:
  - `OUTPUT_DIR = BASE_DIR` (module constant)
  - `GRAPH_FILE = BASE_DIR / "graph.png"`
  - `INDEX_FILE = BASE_DIR / "index.html"`
  - `load_history(path: Path) -> list[dict]` — reads CSV, returns list of dicts.
  - `build_series(rows: list[dict]) -> dict[str, tuple[list[str], list[int]]]` — maps `"STATE Variant"` → (`timestamps`, `counts`).
  - `render_graph(series: dict, out_path: Path) -> Path`
  - `render_html(series: dict, graph_file: Path, out_path: Path) -> Path`

- [ ] **Step 1: Write the failing test**

Create `tests/test_graph.py`:

```python
import csv
import tempfile
from pathlib import Path

import graph


def write_history(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "history.csv"
    fieldnames = ["timestamp_utc", "state", "variant", "count", "stock_numbers"]
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


def test_build_series_groups_by_state_variant(tmp_path):
    p = write_history(
        tmp_path,
        [
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"},
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "WA", "variant": "Premium", "count": "1", "stock_numbers": "3"},
            {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "3", "stock_numbers": "1;2;4"},
        ],
    )
    rows = graph.load_history(p)
    series = graph.build_series(rows)
    assert "VIC Dynamic" in series
    assert "WA Premium" in series
    vic = series["VIC Dynamic"]
    assert vic[0] == ["2026-01-01 00:00:00 UTC", "2026-01-01 00:10:00 UTC"]
    assert vic[1] == [2, 3]


def test_render_graph_creates_png(tmp_path):
    p = write_history(tmp_path, [{"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"}])
    series = graph.build_series(graph.load_history(p))
    out = tmp_path / "graph.png"
    result = graph.render_graph(series, out)
    assert result.exists()
    assert result.suffix == ".png"
    assert out.stat().st_size > 0


def test_render_html_embeds_graph(tmp_path):
    p = write_history(tmp_path, [{"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"}])
    series = graph.build_series(graph.load_history(p))
    gpath = tmp_path / "graph.png"
    graph.render_graph(series, gpath)
    out = tmp_path / "index.html"
    graph.render_html(series, gpath, out)
    assert out.exists()
    text = out.read_text()
    assert "graph.png" in text
    assert "VIC Dynamic" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_graph.py -v`
Expected: FAIL — `graph` module not found/imports fail.

- [ ] **Step 3: Write `graph.py`**

```python
#!/usr/bin/env python3
"""Render history.csv into graph.png and index.html for GitHub Pages."""

from __future__ import annotations

import csv
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
GRAPH_FILE = BASE_DIR / "graph.png"
INDEX_FILE = BASE_DIR / "index.html"
HISTORY_FILE = BASE_DIR / "history.csv"

COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#393b79", "#9c9ede",
]


def load_history(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def build_series(rows: list[dict]) -> dict[str, tuple[list[str], list[int]]]:
    series: dict[str, tuple[list[str], list[int]]] = {}
    for r in rows:
        key = f"{r['state']} {r['variant']}"
        if key not in series:
            series[key] = ([], [])
        series[key][0].append(r["timestamp_utc"])
        series[key][1].append(int(r["count"]))
    return series


def render_graph(series: dict[str, tuple[list[str], list[int]]], out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (label, (timestamps, counts)) in enumerate(sorted(series.items())):
        color = COLORS[i % len(COLORS)]
        ax.plot(range(len(counts)), counts, marker="o", label=label, color=color)
    ax.set_xticks([])
    ax.set_xlabel("Poll over time")
    ax.set_ylabel("Units available")
    ax.set_title("BYD Atto 2 stock over time (by state & variant)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def render_html(
    series: dict[str, tuple[list[str], list[int]]],
    graph_file: Path,
    out_path: Path,
) -> Path:
    rows_html = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{counts[-1] if counts else 0}</td></tr>"
        for label, (_, counts) in sorted(series.items())
    )
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BYD Atto 2 Stock Monitor</title>
<style>
body {{ font-family: sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; }}
h1 {{ font-size: 1.5rem; }}
img {{ max-width: 100%; height: auto; }}
table {{ border-collapse: collapse; margin-top: 1rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
</style>
</head>
<body>
<h1>BYD Atto 2 Stock Monitor</h1>
<p>Latest counts by state &amp; variant:</p>
<table>
<tr><th>State / Variant</th><th>Latest count</th></tr>
{rows_html}
</table>
<p><img src="{graph_file.name}" alt="BYD Atto 2 stock over time"></p>
</body>
</html>
"""
    out_path.write_text(content)
    return out_path


def main() -> int:
    if not HISTORY_FILE.exists():
        print("No history.csv yet; nothing to render.", flush=True)
        return 0
    rows = load_history(HISTORY_FILE)
    series = build_series(rows)
    render_graph(series, GRAPH_FILE)
    render_html(series, GRAPH_FILE, INDEX_FILE)
    print(f"Rendered {len(series)} series to {GRAPH_FILE.name} and {INDEX_FILE.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_graph.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run graph against real history**

Run: `uv run python monitor.py && uv run python graph.py`
Expected: `graph.png` and `index.html` written; `graph.png` non-empty.

- [ ] **Step 6: Commit**

```bash
git add graph.py tests/test_graph.py graph.png index.html
git commit -m "feat: render stock history as graph.png and index.html"
```

---

### Task 4: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/monitor.yml`
- Modify: `README.md` (scheduled-run note + Pages URL placeholder)

**Interfaces:**
- Consumes: `monitor.py`, `graph.py`, `pyproject.toml`, repo `develop`→`main`.
- Produces: A workflow that on schedule and `workflow_dispatch` runs the monitor + graph and commits results back.

- [ ] **Step 1: Write `.github/workflows/monitor.yml`**

```yaml
name: monitor

on:
  schedule:
    - cron: "*/10 * * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: monitor
  cancel-in-progress: false

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Sync deps
        run: uv sync

      - name: Run monitor
        env:
          TO_EMAIL: ${{ secrets.TO_EMAIL }}
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
        run: uv run python monitor.py || true

      - name: Regenerate graph
        run: uv run python graph.py

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add history.csv state.json notifications.log graph.png index.html
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: update stock history and graph [skip ci]"
            git push
          fi
```

- [ ] **Step 2: Rename default branch to `main` (target of Pages)**

Run:
```bash
git branch -m develop main
```
Then push all branches. (Requires the GitHub remote — step within Task 5.)

- [ ] **Step 3: Update README with schedule + Pages placeholder**

Append to README:

```markdown
## Scheduled run

The monitor and graph run automatically via GitHub Actions every 10 minutes.
The generated history, graph and page are committed back to the repo and
served on GitHub Pages at:

    https://<your-user>.github.io/byd-stock-monitor/

(Set the Pages source to "Deploy from a branch" → `main` → `/` root.)
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/monitor.yml README.md
git commit -m "feat: add GitHub Actions scheduled monitor workflow"
```

---

### Task 5: Local repo → GitHub (create repo, push, enable Pages)

**Files:** none (GitHub remote + settings)

**Interfaces:**
- Consumes: final repo state on `main`.
- Produces: public GitHub repo `byd-stock-monitor`, remote `origin`, Pages enabled serving `/` root.

- [ ] **Step 1: Authenticate GitHub CLI**

Run: `gh auth login`
Expected: logged into a GitHub account.

- [ ] **Step 2: Create the repo**

Run:
```bash
gh repo create byd-stock-monitor --public --source=. --push
```
Expected: repo created, `origin` set, code pushed to `main`.

- [ ] **Step 3: Enable GitHub Pages (branch → root)**

Run:
```bash
gh api repos/{owner}/byd-stock-monitor/pages \
  -X POST -f "source[branch]=main" -f "source[path]=/"
```
(replace `{owner}` with the GitHub username).

Expected: Pages enabled; URL `https://<owner>.github.io/byd-stock-monitor/`.

- [ ] **Step 4: Verify workflow runs on schedule**

Open Actions tab / run `workflow_dispatch` once manually. Then within ~10 min,
`history.csv`, `graph.png`, `index.html` should be updated in the repo by the bot commit.

- [ ] **Step 5: Confirm graph accessible via Pages**

Visit `https://<owner>.github.io/byd-stock-monitor/` — should render the page
with the graph image.

- [ ] **Step 6: Update README Pages URL with real value**

Replace the `https://<your-user>.github.io/byd-stock-monitor/` placeholder with
the actual URL, commit, push.

```bash
git add README.md
git commit -m "docs: set real GitHub Pages URL"
git push
```